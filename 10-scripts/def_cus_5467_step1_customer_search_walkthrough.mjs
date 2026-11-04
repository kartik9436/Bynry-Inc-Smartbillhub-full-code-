// ── Trace ──────────────────────────────────────────────
// Change:  DEF-CUS-5467 (step 1 could not search for an existing customer, so
//          every build minted a new one and the clerk retyped what was already
//          on file) · DEF-MET-5438 (the party kind is NOT the owner
//          classification) · DEF-MET-5093 (the identifier the account door
//          refuses to open without).
// Rules:   BR-CUS-1022 · BR-CUS-1023 · BR-CUS-1024 (match first; a phone MINTS
//          and may not MATCH) · BR-CUS-019 (the clerk's explicit answer wins) ·
//          B14 rule 31 (no database id on screen) · rule 33 (on-screen text is
//          capped by what it is for) · rule 42 (built from the drawing as an
//          image) · hard-won law 6 (no gate in this repo reads rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT THE VITEST SUITE CANNOT.
//
// The 26 cases in `NewConnectOwnerStep.test.tsx` hand the component a search
// state and assert what it draws. **They never ask the server anything**, so
// they cannot tell you that `GET /customers?q=` exists, that it is reachable
// from this screen, that it is tenant-scoped, or that a real customer in the
// demo tenant comes back with a number a clerk can read. That is what this
// does: it types a name a real customer has and reports WHAT CAME BACK.
//
// ⚠ AND THE ANSWERS DO NOT SURVIVE A RELOAD (`BR-MET-112` — nothing is written
// until the last step, so the whole wizard is browser state). Every step below
// CLICKS; navigating by URL would capture an empty screen and call it a pass.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def5467/walk";
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

const page = await browser.newPage({ viewport: { width: 1280, height: 1200 } });

// Every request the screen makes, so the search can be shown to be a SERVER
// search rather than a filter over something already in the browser.
const customerCalls = [];
page.on("request", (req) => {
  const url = req.url();
  if (url.includes("/customers")) customerCalls.push(url);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

await page.goto(`${BASE}/${TENANT}/connections/new?step=1`, { waitUntil: "networkidle" });
await page.waitForSelector("#nc_customer_q", { timeout: 20000 });

for (const width of [1280, 1440]) {
  await page.setViewportSize({ width, height: 1200 });
  await page.waitForTimeout(150);
  const m = await page.evaluate(() => {
    const finder = document.querySelector("[data-customer-finder]");
    return {
      present: finder !== null,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      label: document.querySelector('label[for="nc_customer_q"]')?.innerText.trim() ?? "",
      // ⚠ `SegmentedField` puts its id on the radios' NAME and on the
      // label, and never on a DOM id — so `#nc_party_kind` matches nothing and
      // a check written that way is INCAPABLE OF PASSING (hard-won law 7).
      // Found by running this walkthrough, which is the only thing that could.
      partyKind: document.querySelectorAll('input[name="nc_party_kind"]').length,
    };
  });
  say(`@${width}: finder ${m.present} · party kind ${m.partyKind} · label "${m.label}" · page overflow ${m.overflow}px`);
  check(`@${width} the customer search is on step 1`, m.present);
  check(`@${width} the party kind offers both choices`, m.partyKind === 2, `${m.partyKind} radios`);
  check(`@${width} the page does not scroll sideways`, m.overflow <= 0, `${m.overflow}px`);
  await page.screenshot({ path: `${OUT}/step1-${width}.png`, fullPage: true });
}

await page.setViewportSize({ width: 1440, height: 1200 });

// ══════════════════════════════════════════════════════════════════════════
// 1 · UNSTATED IS A REAL ANSWER, AND THE STEP SAYS SO RATHER THAN GUESSING
// ══════════════════════════════════════════════════════════════════════════
await page.fill("#nc_owner_name", "Ridge Property LLC");
await page.waitForTimeout(150);
const beforeKind = await page.evaluate(() => ({
  shortfall: document.querySelector("[data-owner-shortfall]")?.innerText.trim() ?? "",
  taxId: document.querySelector("#nc_tax_id") !== null,
  ssn: document.querySelector("#nc_ssn") !== null,
}));
say(`name typed, no party kind → shortfall "${beforeKind.shortfall}"`);
check("the step names the MISSING DROPDOWN, not the missing evidence",
  beforeKind.shortfall.toLowerCase().includes("person or company"), beforeKind.shortfall);
check("no identifier field is offered before a kind is stated",
  !beforeKind.taxId && !beforeKind.ssn);

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE IDENTIFIER IS PER KIND, AND THE WRONG ONE IS NOT OFFERED
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE RADIO ITSELF IS NOT VISIBLE — `.seg` hides the real input and the
// `<span>` beside it is what a person sees and clicks. Playwright refuses to
// click an invisible element, which is the RIGHT refusal: a control a person
// cannot see is a control they cannot use. So click the LABEL, which is what
// the clerk clicks, and let the browser drive the input.
await page.click('label.seg-opt:has(input[name="nc_party_kind"][value="company"])');
await page.waitForTimeout(200);
const asCompany = await page.evaluate(() => ({
  taxId: document.querySelector("#nc_tax_id") !== null,
  ssn: document.querySelector("#nc_ssn") !== null,
  shortfall: document.querySelector("[data-owner-shortfall]")?.innerText.trim() ?? "",
}));
say(`party kind = company → Tax ID ${asCompany.taxId} · SSN ${asCompany.ssn} · shortfall "${asCompany.shortfall}"`);
check("a company is asked for its Tax ID", asCompany.taxId);
check("a company is NOT asked for a Social Security number", !asCompany.ssn);

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE SEARCH IS THE SERVER'S — and this is the part no unit test can do
// ══════════════════════════════════════════════════════════════════════════
// ⚠ A REAL CUSTOMER IN THE DEMO TENANT, NOT A LETTER. The first draft
// defaulted to "a" — ONE character, below `MIN_CUSTOMER_SEARCH_CHARS`, so the
// search never ran and the attach walk was skipped. It failed loudly rather
// than passing wrongly, which is the right way round, but a walkthrough whose
// default cannot exercise its own subject is a walkthrough nobody re-runs.
// `C-00003 Clara Castillo` is seeded by `10-scripts/03-seed_demo.py`.
const TERM = process.env.TERM_Q ?? "Castillo";
customerCalls.length = 0;
await page.fill("#nc_customer_q", TERM);
await page.waitForTimeout(1500);
const searched = await page.evaluate(() => {
  const rows = [...document.querySelectorAll('[data-customer-state="matches"] li')].map((li) =>
    li.innerText.replace(/\s+/g, " ").trim(),
  );
  return {
    rows,
    tooShort: document.querySelector('[data-customer-state="too-short"]') !== null,
    noMatch: document.querySelector('[data-customer-state="no-match"]') !== null,
    failed: document.querySelector('[data-customer-state="search-failed"]') !== null,
  };
});
say(`searched "${TERM}" → ${customerCalls.length} request(s): ${customerCalls.join(" ")}`);
say(`  ${searched.rows.length} match(es): ${JSON.stringify(searched.rows.slice(0, 5))}`);
say(`  tooShort=${searched.tooShort} noMatch=${searched.noMatch} failed=${searched.failed}`);
check("the search went to the SERVER", customerCalls.length > 0, `${customerCalls.length}`);
check("the search did not fail", !searched.failed);
check("the screen states one of: matches, no match, or too short",
  searched.rows.length > 0 || searched.noMatch || searched.tooShort);

// ⚠ B14 RULE 31, MEASURED AGAINST WHAT IS ACTUALLY ON THE PAGE. A uuid printed
// as a visible value is the defect; a uuid in a `key` or a `data-` attribute is
// not. `innerText` is the right surface to ask, and `innerHTML` is not.
const uuidOnScreen = await page.evaluate(() => {
  const text = document.body.innerText;
  const m = text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
  return m === null ? null : m[0];
});
check("no database id is visible anywhere on the step", uuidOnScreen === null, uuidOnScreen ?? "");
await page.screenshot({ path: `${OUT}/search.png`, fullPage: true });

// ══════════════════════════════════════════════════════════════════════════
// 4 · ATTACH — *"if found, attach and do not retype"*
// ══════════════════════════════════════════════════════════════════════════
if (searched.rows.length > 0) {
  await page.click('[data-customer-state="matches"] li button');
  await page.waitForTimeout(300);
  const attached = await page.evaluate(() => ({
    panel: document.querySelector("[data-customer-attached]") !== null,
    number: document.querySelector("[data-customer-no]")?.innerText.trim() ?? "",
    name: document.querySelector("#nc_owner_name")?.value ?? "",
    taxId: document.querySelector("#nc_tax_id") !== null,
    ssn: document.querySelector("#nc_ssn") !== null,
    licence: document.querySelector("#nc_driving_licence") !== null,
    shortfall: document.querySelector("[data-owner-shortfall]")?.innerText.trim() ?? "",
    uuid: /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(document.body.innerText),
  }));
  say(`attached → number "${attached.number}" · name "${attached.name}" · shortfall "${attached.shortfall}"`);
  check("the attached customer's DETAILS are shown", attached.panel && attached.number !== "");
  check("the customer NUMBER is shown and no uuid is", !attached.uuid, attached.number);
  check("the owner's name was filled in rather than retyped", attached.name !== "");
  check("NO identifier is asked for once a customer is attached",
    !attached.taxId && !attached.ssn && !attached.licence);
  check("the identity shortfall is cleared by the attachment", attached.shortfall === "");
  await page.screenshot({ path: `${OUT}/attached.png`, fullPage: true });

  // The way back out. A clerk who attached the wrong customer must not be stuck.
  await page.click("[data-customer-attached] button");
  await page.waitForTimeout(250);
  const detached = await page.evaluate(() => ({
    finder: document.querySelector("#nc_customer_q") !== null,
    panel: document.querySelector("[data-customer-attached]") !== null,
  }));
  check("Change returns the step to searching", detached.finder && !detached.panel);
} else {
  say("SKIPPED the attach walk — the search returned no rows for this term.");
  say("  Set TERM_Q to a name the demo tenant actually holds and re-run.");
  failures += 1;
}

say(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
