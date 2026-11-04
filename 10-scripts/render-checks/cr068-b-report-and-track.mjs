/**
 * RENDERED-OUTPUT CHECK — CR-068 wave B, "Report a problem and track it".
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*. A story is not signed off
 * until this has run green against a running product.
 *
 * ⚠ **AND B14 RULE 36 GAVE IT A SECOND JOB (PO 2026-09-04).** Eight screens
 * shipped that day off the house style and every one had passed every gate,
 * because a suite that asserts on text content cannot see a colour, a tier or
 * a column so narrow the text wraps one word per line. So this script reads
 * COMPUTED STYLE and GEOMETRY as well as words: the commit button's tier, the
 * brand colour on the current timeline step, and the width of every cell that
 * holds a sentence.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cwpb          # or createdb + migrate + seed
 *   DATABASE_URL=…/sbh_cwpb python3 06-backend/manage.py seed_portal_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cwpb" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8078 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4278 API_PROXY_TARGET=http://127.0.0.1:8078 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4278 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-b-report-and-track.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen. And it WRITES — every report it sends is
 * a real row; clone a database rather than pointing it at a shared one.
 *
 * ── WHAT IT CLICKS (the wave B demo script, 10-execution-plan.md) ─────────
 *   1  From /pine-hill/portal, *Report a problem →*. Pick a leak or a burst,
 *      type the notes, the name and the phone, send. The photo picker is HELD
 *      and there is no file input.
 *   2  Report sent: SR-26-00xx, the time, near 1408 Elm St, and the four-step
 *      *what happens now* with step two current. ⚠ **THIS READ `RP-26-04xx`
 *      UNTIL `CR-072` (2026-09-04).** The report IS the service request now;
 *      the `RP-` series is the utility's own record and is never handed out.
 *   3  A smell of gas on a fresh form: a phone number, and NOTHING created —
 *      asserted by counting rows through the API before and after.
 *   4  Staff: the requests list shows the report with channel *Customer
 *      portal*; the detail's Interruption section **opens** the interruption
 *      (`CR-072` — a stranger's form no longer does), moves it to *crew on
 *      site* and sets the affected area Elm St 1400–1500.
 *   5  Guest: Track, reference + 78702 → the kind, the place and *Crew on
 *      site* — and the RESPONSE BODY carries no customer field.
 *   6  Six wrong pairs from one address lock for fifteen minutes; a CORRECT
 *      pair from that address is still refused; the same pair on /oak-ridge is
 *      not locked.
 *   7  The affected set: 1408 Elm St and 1412 Elm St are in it, 22 Palm Ct is
 *      not (asserted in step 4, where the clerk sets the stretch).
 *   8  The 61st report inside a minute is refused in five or six words —
 *      LAST, and from its own address, because the throttle it trips is
 *      counted per address and would otherwise 429 every step after it.
 *   9  The utilities COMPILED (computed style), and no column wraps one word
 *      per line (B14 rule 36 breach f).
 *  10  No uuid and no rule id in anything a visitor or a clerk reads.
 *  11  MEASURED, NOT ASSERTED: the report and track round trips, printed
 *      against RT-7 and RT-1 rather than claimed to meet them.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4278";
const TENANT = "pine-hill";
const OTHER = "oak-ridge";
const EMAIL = process.env.SMOKE_EMAIL ?? "sarah@pinehillwp.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pin3Hill!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-b";
const VIEWPORT = { width: 1440, height: 1000 };
const PORTAL = `${BASE}/${TENANT}/portal`;

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];
const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Fill the report form on whatever page is open.
 *
 * ⚠ THE REPORTER'S NAME IS AN ARGUMENT, and that is not decoration: step 4
 * finds the clerk's row by searching for *Okafor* and taking the NEWEST, so
 * the second report of step 3 has to belong to somebody else or the clerk
 * would drive the wrong interruption and step 5 would read the wrong status.
 */
async function fillReport(page, kind, where, notes, who = "D. Okafor", phone = "(512) 555-7730") {
  await page.click(`label[data-radio="${kind}"] input`);
  await page.fill("#cwp006-where", where);
  await page.fill("#cwp006-notes", notes);
  await page.fill("#cwp006-name", who);
  await page.fill("#cwp006-phone", phone);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const guest = await context.newPage();
  guest.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-b: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · the front page's card now GOES somewhere ══════════════════════
  console.log("\n── 1 · Report a problem → , from the front page ──");
  await guest.goto(PORTAL, { waitUntil: "networkidle" });
  await guest.waitForSelector("[data-errand]", { timeout: 20000 });
  const reportCard = guest.locator('[data-errand="report_problem"] a');
  check(
    (await reportCard.count()) === 1,
    "the Report a problem card is a LINK now, not a held button (law 2: built is wired)",
  );
  await reportCard.click();
  await guest.waitForSelector('[data-screen="CWP-006"]', { timeout: 20000 });
  check(
    (await guest.locator("body").getAttribute("data-screen-id")) === "CWP-006",
    "the screen carries its id: CWP-006 on <body>",
  );
  const kinds = await guest
    .locator("[data-radio]")
    .evaluateAll((n) => n.map((e) => e.getAttribute("data-radio")));
  check(kinds.length === 6, `six kinds as a radio list, never a wall of boxes (r10 rule 9): ${kinds.length}`);
  check(
    (await guest.locator('input[type="checkbox"]').count()) === 0,
    "no checkbox anywhere on the form",
  );
  check(
    (await guest.locator('input[type="file"]').count()) === 0 &&
      (await guest.locator('[data-photo-picker="held"]').count()) === 1,
    "the photo picker is HELD with its reason and there is NO file input (CR-068 §2b)",
  );
  await guest.screenshot({ path: join(OUT, "1-report-form.png"), fullPage: true });

  await fillReport(
    guest,
    "leak_or_burst",
    "1408 Elm St, Austin TX 78702",
    "Water coming up through the pavement outside number 1412, been going since about seven...",
  );
  await guest.click('button:has-text("Send this report")');

  // ═════ 2 · the reference a stranger keeps ═══════════════════════════════
  console.log("\n── 2 · report sent: the reference and the four steps ──");
  await guest.waitForSelector('[data-screen="CWP-007"]', { timeout: 20000 });
  const reference = (await guest.locator("[data-reference]").innerText()).trim();
  // ⚠ **THIS TESTED `/^RP-/` UNTIL `CR-072`.** One press of Send wrote two rows
  // and the stranger was handed the number of the one that was not their
  // request. One row now, and its number is what they keep.
  check(/^SR-\d{2}-\d{4}$/.test(reference), `the reference reads ${reference}`);
  check(
    (await guest.locator('[data-kv="where"]').innerText()).includes("1408 Elm St"),
    "it says where",
  );
  check(
    (await guest.locator('[data-kv="what"]').innerText()).includes("A leak or a burst"),
    "it says what",
  );
  const steps = await guest
    .locator("[data-timeline-step]")
    .evaluateAll((n) => n.map((e) => e.getAttribute("data-timeline-step")));
  check(
    JSON.stringify(steps) === JSON.stringify(["done", "current", "future", "future"]),
    `four steps with step two current: ${steps.join(" · ")}`,
  );
  check(
    (await guest.locator("body").innerText()).includes("rather hear twice"),
    "the closing line invites a second report",
  );
  await guest.screenshot({ path: join(OUT, "2-report-sent.png"), fullPage: true });

  // ═════ 3 · a smell of gas: a phone number, and nothing created ══════════
  console.log("\n── 3 · a smell of gas routes, and creates NOTHING ──");
  const before = await guest.request.post(`${BASE}/api/${TENANT}/portal/public/track`, {
    data: { reference, second_fact: "78702" },
  });
  check(before.status() === 200, "the report we just made is trackable, so the counter below is real");

  await guest.goto(`${PORTAL}/report`, { waitUntil: "networkidle" });
  await fillReport(guest, "gas_smell", "1408 Elm St, Austin TX 78702", "Strong smell by the meter.");
  await guest.click('button:has-text("Send this report")');
  await guest.waitForSelector('[data-routed="gas_smell"]', { timeout: 20000 });
  const routedText = await guest.locator('[data-routed="gas_smell"]').innerText();
  check(routedText.includes("(512) 555-0100"), "the page answers with the emergency number");
  check(routedText.includes("Nothing was sent"), "and says nothing was sent or recorded");
  check(
    !/(RP|SR)-\d{2}-\d{4}/.test(routedText),
    "no reference of either series, because there is nothing to reference",
  );
  await guest.screenshot({ path: join(OUT, "3-gas-routed.png"), fullPage: true });

  // The DATABASE half of TC-3: the next reference the series hands out is the
  // one after ours, so the gas form consumed nothing. ⚠ Since `CR-072` the
  // series being counted is `SR-`, which every request draws from — the gap is
  // still exactly one because nothing else writes between these two sends.
  await guest.goto(`${PORTAL}/report`, { waitUntil: "networkidle" });
  await fillReport(
    guest,
    "low_pressure",
    "1412 Elm St, Austin TX 78702",
    "Barely a trickle.",
    "R. Mensah",
    "(512) 555-7731",
  );
  await guest.click('button:has-text("Send this report")');
  await guest.waitForSelector('[data-screen="CWP-007"]', { timeout: 20000 });
  const next = (await guest.locator("[data-reference]").innerText()).trim();
  const gap = Number(next.slice(-4)) - Number(reference.slice(-4));
  check(gap === 1, `the gas form consumed no number: ${reference} → ${next} (gap ${gap})`);

  // ═════ 4 · the clerk's worklist and the Interruption section ════════════
  console.log("\n── 4 · a clerk sees it with channel Customer portal ──");
  const staff = await context.newPage();
  await staff.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await staff.fill("#signin-email", EMAIL);
  await staff.fill("#signin-password", PASSWORD);
  await staff.click('button[type="submit"]');
  await staff.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  await staff.goto(`${BASE}/${TENANT}/requests`, { waitUntil: "networkidle" });
  await staff.waitForSelector("table", { timeout: 20000 });
  const listText = await staff.locator("body").innerText();
  check(
    listText.includes("Customer portal"),
    "the requests list shows channel *Customer portal* — the first rows ever to carry it",
  );
  check(listText.includes("D. Okafor"), "and the reporter, who is not a customer");
  await staff.screenshot({ path: join(OUT, "4-requests-list.png"), fullPage: true });

  // ⚠ **THE NEWEST ROW, NOT THE FIRST.** The list is ordered oldest first
  // (B19 §12.1: *"the oldest thing waiting is the thing to look at"*), and this
  // script is not the first report Okafor has ever filed on this database — a
  // second run would otherwise drive the FIRST run's interruption.
  const rows = await staff.request.get(
    `${BASE}/api/${TENANT}/service-requests?q=Okafor&page_size=200`,
  );
  const body = await rows.json();
  const results = body.results ?? body.items ?? [];
  const requestId = results[results.length - 1]?.id;
  check(requestId !== undefined, `the worklist row is reachable by id (${results.length} match Okafor)`);

  await staff.goto(`${BASE}/${TENANT}/requests/${requestId}?tab=location`, {
    waitUntil: "networkidle",
  });
  await staff.waitForSelector('[data-panel-name="interruption"]', { timeout: 20000 });
  check(true, "the detail's Location tab carries an Interruption section (no new screen id — R13)");
  // ⚠ **THIS STEP IS NEW AND IT IS THE RULING (`CR-072`).** The report used to
  // arrive with an interruption already open, because the guest form wrote one.
  // A stranger cannot settle whether something is an outage, so a CLERK opens
  // it — and until they do there is no status to move.
  check(
    (await staff.locator('[data-panel-name="interruption"]').innerText()).includes(
      "Nobody has opened an interruption",
    ),
    "a fresh report has NO interruption, and the section says so rather than 404ing",
  );
  await staff.click("button[data-open-interruption]");
  await staff.waitForSelector('button[data-move-to="crew_on_site"]', { timeout: 20000 });
  check(
    /RP-\d{2}-\d{4}/.test(
      await staff.locator("[data-interruption-reference]").innerText(),
    ),
    "the clerk's own record carries the RP- number — a clerk's vocabulary, never the guest's",
  );
  await staff.click('button[data-move-to="crew_on_site"]');
  // ⚠ WAIT FOR THE SERVER'S ANSWER, not for the click. The status button
  // DISAPPEARS once the interruption is in that state — the section offers the
  // states it is not in — so its absence is the signal the write landed.
  await staff.waitForSelector('button[data-move-to="crew_on_site"]', {
    state: "detached",
    timeout: 20000,
  });
  check(
    (await staff.locator('[data-panel-name="interruption"]').innerText()).includes("Crew on site"),
    "the clerk moved it to *crew on site* without touching a customer's page",
  );
  await staff.fill("#interruption-street", "Elm St");
  await staff.fill("#interruption-from", "1400");
  await staff.fill("#interruption-to", "1500");
  await staff.click('button:has-text("Set the stretch")');
  await staff.waitForSelector("[data-affected]", { timeout: 20000 });
  const affected = await staff
    .locator("[data-affected]")
    .evaluateAll((n) => n.map((e) => e.getAttribute("data-affected")).sort());
  check(
    JSON.stringify(affected) === JSON.stringify(["1408 Elm St", "1412 Elm St"]),
    `step 8 · the affected set is ${affected.join(" · ")}`,
  );
  check(!affected.includes("22 Palm Ct"), "and 22 Palm Ct is NOT in it");
  await staff.screenshot({ path: join(OUT, "5-interruption-section.png"), fullPage: true });

  // ═════ 5 · tracking: progress, and never data ═══════════════════════════
  console.log("\n── 5 · track: the status, and nothing about a customer ──");
  await guest.goto(`${PORTAL}/track`, { waitUntil: "networkidle" });
  await guest.waitForSelector('[data-screen="CWP-012"]', { timeout: 20000 });
  await guest.fill("#cwp012-reference", reference);
  await guest.fill("#cwp012-second-fact", "78702");
  await guest.click('button:has-text("Look it up")');
  await guest.waitForSelector('[data-kv="now"]', { timeout: 20000 });
  const panel = await guest.locator('[data-kvlist]').innerText();
  check(panel.includes("Crew on site"), "the guest sees *Crew on site* without signing in");
  check(panel.includes("A leak or a burst"), "and what it is");
  check(!panel.includes("Okafor"), "and NOT the name on the report");
  await guest.screenshot({ path: join(OUT, "6-track-found.png"), fullPage: true });

  // ⚠ ASSERTED ON THE RESPONSE BODY, NOT ON THE PAGE (US-CWP-010 TC-4). A
  // field that is served and merely not drawn is served.
  const tracked = await guest.request.post(`${BASE}/api/${TENANT}/portal/public/track`, {
    data: { reference, second_fact: "78702" },
  });
  const trackedBody = await tracked.json();
  const keys = Object.keys(trackedBody).sort();
  check(
    JSON.stringify(keys) ===
      JSON.stringify([
        "expected_back_on",
        "kind",
        "location_text",
        "reference",
        "reported_at",
        "resolved_at",
        "series",
        "status",
      ]),
    `the response body carries eight keys and no customer field: ${keys.join(", ")}`,
  );
  const flat = JSON.stringify(trackedBody);
  check(!flat.includes("Okafor") && !flat.includes("5557730") && !flat.includes("555-7730"),
    "no name and no phone in the body");
  check(!/"(balance|amount|owing|account|customer|name|phone|id)"/.test(flat),
    "no balance, no account, no id");
  // ⚠ **THIS INVERTED ON 2026-09-04 (`CR-072`).** It read `!flat.includes("SR-")`
  // — correct while the SR- number was the OTHER reference the same act created
  // and had to be withheld. There is one reference now and it IS the `SR-`;
  // what must never reach a guest is the utility's own `RP-`.
  check(!flat.includes("RP-"), "and never the utility's own operational reference");

  // ═════ 6 · the lockout ═════════════════════════════════════════════════
  console.log("\n── 6 · six wrong pairs lock for fifteen minutes ──");
  // ⚠ **ITS OWN ADDRESS.** The lock is per tenant, per form, PER ADDRESS and it
  // lasts fifteen minutes — so run from the shared context and every later step
  // that looks a reference up is refused for a reason that has nothing to do
  // with what it is testing. This context is the guesser; `guest` is not.
  const guesserContext = await browser.newContext({
    viewport: VIEWPORT,
    extraHTTPHeaders: { "X-Forwarded-For": "198.51.100.10" },
  });
  const guesser = await guesserContext.newPage();
  let sixth = null;
  for (let i = 0; i < 6; i += 1) {
    sixth = await guesser.request.post(`${BASE}/api/${TENANT}/portal/public/track`, {
      // ⚠ `SR-` since `CR-072`: an `RP-` is not a series a guest is ever handed,
      // so guessing one proves nothing about a guest-facing lockout.
      data: { reference: `SR-26-99${String(10 + i)}`, second_fact: "78702" },
    });
  }
  const sixthBody = await sixth.json();
  check(sixthBody.message_key === "portal.track.locked", `the sixth is LOCKED (${sixthBody.message_key})`);
  const stillRefused = await guesser.request.post(`${BASE}/api/${TENANT}/portal/public/track`, {
    data: { reference, second_fact: "78702" },
  });
  const stillBody = await stillRefused.json();
  check(
    stillBody.message_key === "portal.track.locked",
    "a CORRECT pair from the same address is still refused",
  );
  const otherTenant = await guesser.request.post(`${BASE}/api/${OTHER}/portal/public/track`, {
    data: { reference: "SR-26-9999", second_fact: "78702" },
  });
  const otherBody = await otherTenant.json();
  check(
    otherBody.message_key === "portal.track.notFound",
    "and /oak-ridge is NOT locked — the lock is per tenant",
  );
  // The sentence a person reads, on the screen, in five or six words.
  await guesser.goto(`${PORTAL}/track`, { waitUntil: "networkidle" });
  await guesser.fill("#cwp012-reference", reference);
  await guesser.fill("#cwp012-second-fact", "78702");
  await guesser.click('button:has-text("Look it up")');
  await guesser.waitForSelector("[data-refusal]", { timeout: 20000 });
  const refusalText = (await guesser.locator("[data-refusal]").innerText()).trim();
  check(
    refusalText.split(/\s+/).length <= 6,
    `the refusal on screen is ${refusalText.split(/\s+/).length} words: "${refusalText}"`,
  );
  await guesser.screenshot({ path: join(OUT, "7-track-locked.png"), fullPage: true });
  await guesserContext.close();

  // ═════ 8 · the utilities COMPILED, and nothing wraps one word a line ════
  console.log("\n── 8 · computed style: the classes compiled, and the columns are wide enough ──");
  await guest.goto(`${PORTAL}/report`, { waitUntil: "networkidle" });
  await guest.waitForSelector('[data-screen="CWP-006"]', { timeout: 20000 });
  const styles = await guest.evaluate(() => {
    const card = document.querySelector('[data-testid="cwp006-form"]');
    const radio = document.querySelector("[data-radiolist]");
    const consequence = document.querySelector("[data-consequence]");
    // ⚠ THE COMMIT, NOT THE FIRST BUTTON ON THE PAGE. `document.querySelector`
    // was finding the FRAME's held *Sign in* — a secondary — and reporting the
    // form's commit tier as `secondary`. A check that reads the wrong element
    // is worse than no check (DEF-182).
    const commit = document.querySelector('[data-testid="cwp006-form"] button[data-variant]');
    const cs = (el) => (el === null ? null : getComputedStyle(el));
    return {
      cardBorder: cs(card)?.borderTopWidth ?? null,
      cardBackground: cs(card)?.backgroundColor ?? null,
      radioDisplay: cs(radio?.querySelector("label"))?.display ?? null,
      consequenceRule: cs(consequence)?.borderLeftWidth ?? null,
      consequenceColour: cs(consequence)?.borderLeftColor ?? null,
      commitVariant: commit?.getAttribute("data-variant") ?? null,
      commitBackground: cs(commit)?.backgroundColor ?? null,
    };
  });
  check(styles.cardBorder === "1px", `the card's border compiled (${styles.cardBorder})`);
  check(
    styles.cardBackground === "rgb(255, 255, 255)",
    `bg-[white] compiled to a real colour (${styles.cardBackground})`,
  );
  check(styles.radioDisplay === "flex", `the radio rows are flex (${styles.radioDisplay})`);
  check(
    styles.consequenceRule === "4px" && styles.consequenceColour === "rgb(236, 48, 19)",
    `the consequence box carries the TENANT's brand rule (${styles.consequenceRule} ${styles.consequenceColour})`,
  );
  // ⚠ r10 RULE 6, READ FROM THE RENDERED TIER. A sign-in button shipped in the
  // danger colour this morning and every text assertion passed over it.
  check(
    styles.commitVariant === "primary",
    `the commit is the primary tier, never danger (${styles.commitVariant})`,
  );
  check((await guest.evaluate(SIDEWAYS)) === 0, "no sideways scroll at 1440");

  // ⚠ B14 rule 36 breach (f): a column so narrow the text wraps one word per
  // line. Measured, because no test in this repo can see it — text content is
  // identical however it wraps.
  await guest.goto(`${PORTAL}/track`, { waitUntil: "networkidle" });
  await guest.fill("#cwp012-reference", reference);
  await guest.fill("#cwp012-second-fact", "(512) 555-7730");
  await guest.click('button:has-text("Look it up")');
  await guest.waitForSelector('[data-kv="now"]', { timeout: 20000 });
  // ⚠ **WHAT IS MEASURED IS WRAPPING, NOT WIDTH — AND THE FIRST DRAFT OF THIS
  // CHECK GOT THAT WRONG.** It asked for 60px and reported the *What* label at
  // 33px as a failure; *What* is one word and fits on one line at 33px, so the
  // check was flagging a healthy cell. The breach B14 rule 36 names is a cell
  // that renders ONE WORD PER LINE — eleven lines for eleven words — so that is
  // what this counts: lines against words, per cell. A one-word cell is exempt
  // because one word on one line is not a wrap.
  const squeezed = await guest.evaluate(() => {
    const cells = [...document.querySelectorAll("[data-kvlist] dd, [data-kvlist] dt")];
    return cells
      .map((cell) => {
        const style = getComputedStyle(cell);
        const line = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.4;
        const lines = Math.max(1, Math.round(cell.getBoundingClientRect().height / line));
        const words = (cell.textContent ?? "").trim().split(/\s+/).filter(Boolean).length;
        return { text: (cell.textContent ?? "").trim().slice(0, 40), words, lines };
      })
      .filter((c) => c.words > 1 && c.lines >= c.words);
  });
  check(
    squeezed.length === 0,
    squeezed.length === 0
      ? "no cell renders one word per line (B14 rule 36 breach f)"
      : `${squeezed.length} cell(s) render one word per line: ${squeezed
          .map((c) => `"${c.text}" ${c.words}w/${c.lines}L`)
          .join(" · ")}`,
  );
  await guest.screenshot({ path: join(OUT, "8-track-by-phone.png"), fullPage: true });

  // ═════ 9 · nothing internal on a customer's screen ═════════════════════
  console.log("\n── 9 · no uuid and no rule id in anything a person reads ──");
  for (const [name, page] of [["guest", guest], ["staff", staff]]) {
    const text = await page.locator("body").innerText();
    const hit = FORBIDDEN.find((re) => re.test(text));
    check(hit === undefined, `${name}: no internal reference on screen${hit ? ` — ${hit}` : ""}`);
  }

  // ═════ 10 · MEASURED, NOT ASSERTED ═════════════════════════════════════
  console.log("\n── 10 · the response times, printed rather than claimed ──");
  for (let i = 0; i < 24; i += 1) {
    await guest.goto(`${PORTAL}/track`, { waitUntil: "networkidle" });
  }
  const result = await timings.report({
    title: "cr068 wave B — report a problem, and track it",
    targets: [
      { id: "RT-7", match: "/portal/public/reports", p95: 800 },
      { id: "RT-1", match: "/portal/public/track", p95: 400 },
      { id: "RT-1", match: "/portal/public/front", p95: 400 },
    ],
  });
  console.log(
    `   (${result.misses.length} of the three budgets missed; a miss is REPORTED, never rounded — 11-response-times.md §5)`,
  );

  // ═════ 11 · the 61st report in a minute — LAST, own address ═══════════
  console.log("\n── 11 · the 61st report in one minute is refused in six words ──");
  // ⚠ **ITS OWN ADDRESS, AND IT RUNS LAST.** `PublicOnboardingThrottle` counts
  // sixty a minute PER ADDRESS, and every request this script has made so far
  // came from one. Run in the middle and from the shared bucket, this step
  // exhausted the allowance and the four steps after it met 429s that had
  // nothing to do with what they were testing — a check reporting a failure it
  // caused itself. The flood therefore carries `X-Forwarded-For`, which is what
  // DRF's `get_ident` counts, and it is the last thing this script does.
  const fresh = await browser.newContext({
    viewport: VIEWPORT,
    extraHTTPHeaders: { "X-Forwarded-For": "198.51.100.61" },
  });
  const flood = await fresh.newPage();
  let refused = null;
  let accepted = 0;
  for (let i = 0; i < 70 && refused === null; i += 1) {
    const answer = await flood.request.post(`${BASE}/api/${TENANT}/portal/public/reports`, {
      data: {
        kind: "missed_collection",
        location_text: "9 Ash Ln, Austin TX 78702",
        notes: "bin not emptied",
        reporter_name: "A Neighbour",
        reporter_phone: "(512) 555-0000",
      },
    });
    if (answer.status() === 429) refused = answer;
    else accepted += 1;
  }
  const refusedBody = refused === null ? {} : await refused.json();
  check(refused !== null, `the throttle bites after ${accepted} accepted in a minute`);
  check(refusedBody.message_key === "errors.rate-limited", `refused with ${refusedBody.message_key}`);
  await fresh.close();

  await browser.close();
  console.log(`\nscreenshots → ${OUT}`);
  if (failures.length > 0) {
    console.log(`\ncr068-b: ${failures.length} FAILED`);
    for (const f of failures) console.log(`  ⛔ ${f}`);
    process.exit(1);
  }
  console.log("\ncr068-b: all checks passed");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
