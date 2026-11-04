// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-5674 — a clerk could not set an account SUB-TYPE while
//          creating an account, on either of the two screens an account is
//          born on.
// Also:    DEF-CUS-5668 — the accounts list CAN filter by account type; the
//          chip is called *Category*. This walk MEASURES that rather than
//          asserting it, because the whole point of the row is that the
//          capability was reported missing while working.
// Rules:   BR-CUS-067 (the tenant's two-level tree) · `parent_required` ·
//          B2 (`accounts.account_subtype_id` is nullable) · B14 rule 31 ·
//          hard-won law 6 (no gate in this repo reads rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT `AccountSubtypePicker.test.tsx` CANNOT.
//
// Those 12 cases seed a query cache and assert what React draws. **They ask the
// server nothing.** They cannot tell you that `GET /lookups/account_subtypes`
// is reachable from this screen, that it is tenant-scoped, that
// `POST /accounts` accepts `account_subtype`, or that the column ends up SET on
// the row. This drives the wizard with a mouse and then **reads the row back
// out of PostgreSQL**, which is the only witness that the write happened.
//
// ⚠ EVERY STEP CLICKS. The wizard writes nothing until the last step, so it is
// entirely browser state — navigating by URL would photograph an empty screen
// and call it a pass.
//
// USAGE
//   BASE=http://127.0.0.1:8081 node 10-scripts/def_cus_5674_subtype_walkthrough.mjs
// Then read the account back:
//   psql -c "set app.tenant_id='…'; select account_subtype_id from accounts where …"
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8081";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def5654";
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
        const c = join(root, dir, sub);
        if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium found");
}

const say = (...p) => console.log(...p);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });

// Every call the screens make, so a SERVER read can be told from a typed list.
const calls = [];
page.on("request", (r) => {
  const u = r.url();
  if (u.includes("/api/")) calls.push(`${r.method()} ${u.replace(BASE, "")}`);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL}`);

// ═══ A · THE NEW ACCOUNT WIZARD, STEP 1 ═══════════════════════════════════
//
// ⚠ **ENTERED THROUGH THE DOOR, NOT BY URL** (PO 2026-09-17: *"do the Walks as
// user from screens"*). The Accounts blueprint names three doors to this
// wizard, and the list's primary is the one a clerk uses. A walk that types the
// address proves the screen renders and says nothing about whether anybody can
// GET there — which is the half hard-won law 2's mirror is about.
await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.click('text="+ New account"');
await page.waitForURL((u) => u.pathname.includes("/accounts/new"), { timeout: 20000 });
check("the door — `+ New account` on the list opens the wizard", true, page.url().replace(BASE, ""));
await page.waitForSelector("#account_subtype", { timeout: 20000 });
// ⚠ **WAIT FOR THE FETCHED LIST, NOT FOR THE CONTROL.** The first draft read
// the options the moment the `<select>` appeared and got ONE — the placeholder
// — because `GET /lookups/account_subtypes` was still in flight. It reported
// that as a filtering failure, over a screen that was working. A check that
// races the thing it measures reports on its own timing.
await page.waitForFunction(
  () => (document.querySelector("#account_subtype")?.options.length ?? 0) > 1,
  { timeout: 20000 },
);

const readPicker = () =>
  page.$eval("#account_subtype", (el) => ({
    options: [...el.options].map((o) => ({ value: o.value, label: o.textContent.trim() })),
    value: el.value,
    ariaRequired: el.getAttribute("aria-required"),
  }));

// The default category is `residential`, so the list is residential's own.
let picker = await readPicker();
check(
  "the picker exists on the screen an account is born on",
  picker.options.length > 0,
  `${picker.options.length} options`,
);
check(
  "B14 rule 31 — the clerk READS a name, never the stored code",
  picker.options.some((o) => o.label === "Single-family") &&
    !picker.options.some((o) => o.label === "single_family"),
  JSON.stringify(picker.options.map((o) => o.label)),
);
check(
  "it is OPTIONAL — a leading empty option and no aria-required",
  picker.options[0]?.value === "" && picker.ariaRequired === null,
  `first=${JSON.stringify(picker.options[0])} aria-required=${picker.ariaRequired}`,
);
// ⚠ **THE ORDER IS THE SERVER'S AND NOTHING HERE RE-SORTS IT.**
// `AccountSubtypeLookupHandler.search` is `order_by("code", "id")`, so the list
// arrives alphabetically BY CODE — and `accountSubtypesUnder` preserves what it
// is given, exactly as `useAccountCategories` preserves BR-CUS-094's order. A
// walkthrough that asserted a prettier order would be asserting a re-sort this
// product deliberately does not do.
check(
  "filtered by the chosen category — residential's children only",
  picker.options.map((o) => o.value).join(",") === ",multi_family,senior_low_income,single_family",
  picker.options.map((o) => o.value).join(","),
);
await page.screenshot({ path: `${OUT}/A1_step1_residential.png`, fullPage: true });

// Switch the category to Commercial — the list must change with it.
await page.click('label:has-text("Commercial"), [data-segment="commercial"]').catch(async () => {
  await page.click('text="Commercial"');
});
await page.waitForTimeout(400);
picker = await readPicker();
check(
  "changing the category re-fills the child list from the tenant's rows",
  picker.options.map((o) => o.value).join(",") ===
    ",healthcare,institutional_non_profit,large_commercial,small_commercial",
  picker.options.map((o) => o.value).join(","),
);
await page.screenshot({ path: `${OUT}/A2_step1_commercial.png`, fullPage: true });

// Pick one, then correct the category — the incompatible child must CLEAR.
await page.selectOption("#account_subtype", "healthcare");
check("a sub-type can be chosen", (await readPicker()).value === "healthcare");
await page.screenshot({ path: `${OUT}/A3_step1_healthcare_chosen.png`, fullPage: true });

await page.click('text="Industrial"');
await page.waitForTimeout(400);
picker = await readPicker();
check(
  "correcting the category CLEARS the now-incompatible sub-type",
  picker.value === "",
  `value=${JSON.stringify(picker.value)}`,
);
check(
  "…and the list is now industrial's own",
  picker.options.map((o) => o.value).join(",") === ",heavy_industrial,light_industrial",
  picker.options.map((o) => o.value).join(","),
);
await page.screenshot({ path: `${OUT}/A4_step1_cleared.png`, fullPage: true });

check(
  "the list is a SERVER read, not a typed catalogue",
  calls.some((c) => c.includes("/lookups/account_subtypes")),
  calls.filter((c) => c.includes("lookups")).slice(0, 3).join(" · "),
);

// ═══ A2 · DRIVE THE WHOLE WIZARD AND COMMIT ══════════════════════════════
//
// ⚠ **THIS IS THE ONLY PART THAT PROVES THE COLUMN IS WRITTEN.** Everything
// above proves the CONTROL behaves; a control that behaves perfectly and sends
// nothing is hard-won law 2's dead UI. The commit is clicked through all five
// steps because the wizard writes nothing until the last one — its whole state
// is in the browser, so a jump by URL would post an empty form.
const STAMP = `SUBTYPE ${Date.now()}`;
await page.click('text="Commercial"');
await page.waitForTimeout(300);
await page.selectOption("#account_subtype", "small_commercial");
await page.fill("#full_name", STAMP);
// ⚠ **THE STEP-1 GATE IS `BR-CUS-1024` AND IT IS NOT ABOUT THE SUB-TYPE.**
// `Continue` holds until a kind is stated and ONE identifier is on file — PO
// 2026-09-01, *"Without identifier we cannot create Customer ID"*. The
// sub-type is deliberately outside that gate: it is optional, and this walk
// would be worthless if it could not tell the two refusals apart.
await page.click('text="Person"');
await page.fill("#phone", "(512) 555-0199");
await page.waitForTimeout(300);
check(
  "step 1 holds the pair a clerk chose",
  (await readPicker()).value === "small_commercial",
);
await page.screenshot({ path: `${OUT}/A5_step1_ready.png`, fullPage: true });
await page.click('button:has-text("Continue")');

// Step 2 — the unit. An ARIA combobox (BR-SHL-033), so TYPE then PICK.
await page.waitForSelector("#unit_id", { timeout: 20000 });
await page.fill("#unit_id", "U-00101-A");
await page.waitForTimeout(1200);
const picked = await page.evaluate(() => {
  const opt = document.querySelector('[id^="unit_id-opt-"]');
  if (opt === null) return null;
  opt.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
  opt.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  return opt.textContent.trim();
});
check("step 2 — a vacant unit is pickable", picked !== null, String(picked));
await page.waitForTimeout(600);
// BR-CUS-022 — an occupying account with no start date can never be billed,
// so the step asks for both.
await page.fill("#opened_at", "2026-10-01");
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/A5b_step2_unit.png`, fullPage: true });
await page.click('button:has-text("Continue")');

// Steps 3 and 4 — defaults are a real answer; nothing here is the subject.
await page.waitForTimeout(800);
await page.click('button:has-text("Continue")');
await page.waitForTimeout(800);
await page.click('button:has-text("Continue")');

// Step 5 — the review must SHOW the sub-type by name, then commit as a DRAFT
// (a draft occupies nothing, so this walk leaves the unit as it found it).
await page.waitForTimeout(900);
const reviewText = await page.evaluate(() => document.body.innerText);
check(
  "step 5 shows the sub-type by NAME on the screen that says what will be written",
  reviewText.includes("Small commercial"),
  reviewText.includes("small_commercial") ? "shows the RAW CODE — rule 31" : "by name",
);
await page.screenshot({ path: `${OUT}/A6_step5_review.png`, fullPage: true });

const draft = await page.evaluate(() => {
  const label = [...document.querySelectorAll("label")].find((l) =>
    /draft/i.test(l.textContent ?? ""),
  );
  if (label === undefined) return false;
  label.click();
  return true;
});
await page.waitForTimeout(400);
// ⚠ **THE COMMIT BUTTON IS NAMED AFTER THE MODE, so it is FOUND rather than
// typed.** Picking Draft re-words it, and a walkthrough hard-coding
// `Create & activate` would time out on the very choice it just made — the
// "looking at the wrong thing" shape, in a selector.
const labels = await page.evaluate(() =>
  [...document.querySelectorAll("button")].map((b) => b.textContent.trim()),
);
say("step 5 buttons:", JSON.stringify(labels.slice(-4)));
const commit = page.locator("button").filter({ hasText: /Create|Save|Draft/i }).last();
await commit.click();
await page.waitForTimeout(3000);
await page.screenshot({ path: `${OUT}/A7_created.png`, fullPage: true });
say(`created as ${draft ? "DRAFT" : "the default mode"} with full_name = ${STAMP}`);

// ── and LAND ON IT: the account the walk just made, opened from the list ───
await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
await page.waitForTimeout(1800);
const opened = await page.evaluate((stamp) => {
  const row = [...document.querySelectorAll("table tbody tr")].find((tr) =>
    tr.textContent.includes(stamp),
  );
  const link = row?.querySelector("a");
  if (link == null) return null;
  link.click();
  return link.textContent.trim();
}, STAMP);
check("the new account is ON the list and its number opens it", opened !== null, String(opened));
await page.waitForTimeout(2500);
const detail = await page.evaluate(() => document.body.innerText);
check(
  "the account PAGE shows the sub-type it was created with, by NAME",
  detail.includes("Small commercial"),
  detail.includes("small_commercial") ? "RAW CODE on screen — rule 31" : "by name",
);
await page.screenshot({ path: `${OUT}/A8_account_detail.png`, fullPage: true });
say("READ IT BACK:  select a.account_no, s.code from accounts a");
say("               left join account_subtypes s on s.id = a.account_subtype_id");
say(`               join contacts c on c.account_id = a.id where c.full_name = '${STAMP}';`);

// ═══ B · THE ACCOUNTS LIST — the type filter, under the name `Category` ════
//
// `DEF-CUS-5668`. The server declares `category` in `ACCOUNT_FILTERS` and
// applies it as `account_type__code__iexact`, so the chip a clerk sees as
// *Category* IS the account-type filter. This MEASURES that it narrows.
//
// ⚠ **NOTHING HERE IS A HARD-CODED COUNT, AND THE FIRST DRAFT WAS.** It
// asserted `10 of 72` — true when it was written and false thirty seconds
// later, because section A2 above creates a commercial account and the walk
// then failed on its own predecessor's success. A check whose expected value
// its own run invalidates can pass exactly once. Both numbers now come from
// the SERVER on this run, and the assertion is the relationship between them.
async function listCount(query) {
  const url = `${BASE}/api/${TENANT}/accounts?per=200${query}`;
  const body = await page.evaluate(
    (u) => fetch(u, { credentials: "include" }).then((r) => r.json()),
    url,
  );
  return { count: body.count, rows: (body.results ?? []).length, body };
}

await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const all = await listCount("");
const commercial = await listCount("&f.category=commercial");

await page.goto(`${BASE}/${TENANT}/accounts?f.category=commercial&per=200`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(2000);
const drawn = await page.evaluate(() => document.querySelectorAll("table tbody tr").length);

check(
  "the account-TYPE filter NARROWS — fewer accounts come back than the tenant has",
  commercial.count > 0 && commercial.count < all.count,
  `${commercial.count} commercial of ${all.count} total`,
);
check(
  "…and the COUNT MATCHES THE ROWS DRAWN — not merely that the chip renders",
  drawn === commercial.count && commercial.rows === commercial.count,
  `drawn=${drawn} served=${commercial.rows} count=${commercial.count}`,
);
await page.screenshot({ path: `${OUT}/B1_list_commercial.png`, fullPage: true });
say(
  `  ⓘ cross-check against PostgreSQL: select count(*) from accounts a join account_types t ` +
    `on t.id=a.account_type_id where t.code='commercial'  →  expect ${commercial.count}`,
);

// ═══ C · THE SAME SCREEN AS A BILLING CLERK — `DEF-CUS-5677` ══════════════
//
// ⚠ **THIS SECTION IS THE REASON THE WALK EXISTS AT ALL.** Everything above
// ran as a SYSTEM ADMIN and passed. `GET /lookups/{list}` allows only
// `{SYSTEM_ADMIN, EXECUTIVE}` (A4 `settings_lookups`, `DEF-196`), so the role
// that opens accounts all day gets **403** — and a walk that only ever signs in
// as an admin would have certified a control that is dead for its actual user.
// Hard-won law 2's mirror, caught by changing WHO is looking.
const clerkPage = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
const clerkCodes = [];
clerkPage.on("response", (r) => {
  if (r.url().includes("lookups")) clerkCodes.push(r.status());
});
await clerkPage.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await clerkPage.fill("#signin-email", process.env.CLERK_EMAIL ?? "sam.reyes@sample.test");
await clerkPage.fill("#signin-password", process.env.CLERK_PASSWORD ?? PASSWORD);
await clerkPage.click('button[type="submit"]');
await clerkPage.waitForTimeout(4000);
await clerkPage.goto(`${BASE}/${TENANT}/accounts/new?step=1`, { waitUntil: "networkidle" });
await clerkPage.waitForTimeout(3500);
const clerk = await clerkPage.evaluate(() => ({
  role: document.body.innerText.match(/Billing Clerk|System Admin|Executive/)?.[0] ?? null,
  control: document.querySelector("#account_subtype") !== null,
  text: document.body.innerText,
}));
check("the walk is really signed in as a CLERK", clerk.role === "Billing Clerk", String(clerk.role));
check(
  "`DEF-CUS-5677` reproduced — /lookups/* refuses the clerk",
  clerkCodes.includes(403),
  `lookups responses: ${JSON.stringify(clerkCodes)}`,
);
check(
  "BR-SHL-025 — the refusal is STATED, not drawn as an empty dropdown",
  clerk.text.includes("Your role cannot list sub-types.") && clerk.control === false,
  `sentence=${clerk.text.includes("Your role cannot list sub-types.")} control=${clerk.control}`,
);
await clerkPage.screenshot({ path: `${OUT}/C1_clerk_step1.png`, fullPage: true });
await clerkPage.close();

say("");
say(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
