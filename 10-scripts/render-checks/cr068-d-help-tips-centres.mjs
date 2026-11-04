/**
 * RENDERED-OUTPUT CHECK — CR-068 wave D, "Help, tips and where you can walk
 * in", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*. A story is not signed off
 * until this has run green against a running product.
 *
 * ⚠ **AND B14 RULE 36 ADDED A SECOND REASON ON 2026-09-04.** The rule was
 * ratified on eight screens that had passed every gate and were still off the
 * house style, and one of its own findings is the one no test can reach: a
 * column so narrow its text wrapped ONE WORD PER LINE for eleven lines, which
 * every suite passed because text content is identical however it wraps. So
 * this script reads GEOMETRY as well as text — a cell's width against its
 * content — and saves screenshots to be LOOKED at.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwpd --export)"   # ~0.3 s
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_portal_demo
 *
 *   ⚠ **THE CLOCK IS PINNED, AND IT HAS TO BE.** *"Closed today · Opens
 *   Thursday at 9:00am"* and *"Closed 26 November"* are COMPUTED from the
 *   clock and the tenant's holiday calendar and typed by nobody
 *   (`BR-CWP-096`) — which is the rule's whole point and also means the two
 *   sentences can only be SEEN on a Wednesday in November. So the server runs
 *   with `PORTAL_CLOCK_OVERRIDE=2026-11-18T10:00:00`, honoured only under
 *   `DEBUG` and therefore never on a deployed build:
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *   PORTAL_CLOCK_OVERRIDE="2026-11-18T10:00:00" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8069 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4269 API_PROXY_TARGET=http://127.0.0.1:8069 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4269 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-d-help-tips-centres.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ── WHAT IT CLICKS (the wave D demo script, 10-execution-plan.md) ─────────
 *   1  Staff → Settings → Configure → Customer portal → Help & answers:
 *      EIGHT rows, six published, one draft, one NOT SHOWN, with *read this
 *      month*; and the list is the shared `DataTable` — pagination footer,
 *      search box, sortable header (B14 rule 36).
 *   2  Open *Why is my bill higher than last month?*: the language table reads
 *      English PUBLISHED · Español (México) PUBLISHED · Français NEEDS
 *      TRANSLATING · हिन्दी PUBLISHED, and the screen warns there is NO
 *      APPROVAL STEP.
 *   3  Guest `/pine-hill/portal/help`: SIX answers in the back office's order;
 *      the draft and the not-shown are absent and NO COUNT OF WHAT IS HIDDEN
 *      appears. A French browser gets the answer in ENGLISH with a line
 *      saying so.
 *   4  Open the answer three times and press *No* once: the staff count moves
 *      1,204 → 1,207 and the vote is its OWN event.
 *   5  Staff Tips: six tips, FOUR showing today; the freeze tip is off AND out
 *      of season — two independent reasons.
 *   6  Staff Reference data → Service centres: THREE rows with the depot
 *      *shown to customers* off; its editor draws chips, not a wall of
 *      checkboxes (r10 rule 9).
 *   7  Guest *Where you can walk in*: TWO centres; the north counter reads
 *      *Closed today · Opens Thursday at 9:00am* COMPUTED from the clock (the
 *      drawing's *Tuesday* was wrong — DEF-CWP-3604); four of five action rows
 *      say no; the footer holiday is read from the calendar.
 *   8  Hide every centre: the *Visit us* link and the page are absent.
 *      Unpublish every answer: the *Help* link and the card are absent.
 *   9  The utilities COMPILED, read as computed style — including a COLOUR.
 *  10  Nothing internal on screen; no sideways scroll; and the geometry check
 *      rule 36 asked for.
 *  11  MEASURED, NOT ASSERTED: the guest help and centre reads, through
 *      `lib/timings.mjs`, against `11-response-times.md`'s figures.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4269";
const TENANT = "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "sarah@pinehillwp.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pin3Hill!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-d";
const VIEWPORT = { width: 1440, height: 1000 };
const HELP_SETTINGS = `${BASE}/${TENANT}/settings/reference-data/customer-portal/help`;
const TIPS_SETTINGS = `${BASE}/${TENANT}/settings/reference-data/customer-portal/tips`;
const CENTRES_SETTINGS = `${BASE}/${TENANT}/settings/reference-data?list=service_centres`;
const HELP = `${BASE}/${TENANT}/portal/help`;
const VISIT = `${BASE}/${TENANT}/portal/visit`;
const BILL_HIGHER = "why-is-my-bill-higher-than-last-month";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const staff = await context.newPage();
  staff.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-d: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  console.log("clock pinned to Wednesday 18 November 2026 (PORTAL_CLOCK_OVERRIDE, DEBUG only)");

  // ═════ 1 · the answers list ══════════════════════════════════════════════
  console.log("\n── 1 · eight answers, and two of them a customer never sees ──");
  await staff.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await staff.fill("#signin-email", EMAIL);
  await staff.fill("#signin-password", PASSWORD);
  await staff.click('button[type="submit"]');
  await staff.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  await staff.goto(HELP_SETTINGS, { waitUntil: "networkidle" });
  await staff.waitForSelector('[data-screen="CWP-071"]', { timeout: 20000 });
  const rows = await staff.locator("[data-answer-row]").count();
  check(rows === 8, `eight answers in the back office (${rows})`);
  check(
    (await staff.locator('[data-answer-status="published"]').count()) === 6,
    "six of them published",
  );
  check((await staff.locator('[data-answer-status="draft"]').count()) === 1, "one draft");
  check((await staff.locator('[data-answer-status="not_shown"]').count()) === 1, "one not shown");
  // ⚠ THE FIGURE IS THE FIXTURE'S — `US-CWP-071` §4's 1,204 on a fresh seed —
  // but this script is RE-RUNNABLE and step 4 adds three reads every time, so
  // what is asserted here is that the column holds a real, grouped number and
  // what is asserted in step 4 is the MOVEMENT. A hard `1,204` here would pass
  // once and then read as a broken screen for ever after.
  const reads = (await staff.locator(`[data-reads="${BILL_HIGHER}"]`).innerText()).trim();
  check(/^\d{1,3}(,\d{3})+$/.test(reads), `read this month reads ${reads} (1,204 on a fresh fixture)`);
  // B14 rule 36: the SHARED kit, not a hand-rolled table.
  const staffText = await staff.locator("body").innerText();
  check(staffText.includes("Rows per page"), "r10 rule 16: the pagination footer is there");
  check(staffText.includes("1–8 of 8"), "…and it counts what is on the page");
  check(
    (await staff.locator('input[placeholder="Search questions…"]').count()) === 1,
    "r10 rule 12: the toolbar's search box, with this list's own prompt",
  );
  check((await staff.locator(".table-sort").count()) > 0, "r10 rule 13: a sortable header");
  await staff.screenshot({ path: join(OUT, "1-answers-list.png"), fullPage: true });

  // ═════ 2 · the editor, the language table, the warning ═══════════════════
  console.log("\n── 2 · the language a utility is NOT showing, and no approval step ──");
  await staff.click(`[data-answer-row="${BILL_HIGHER}"] >> xpath=ancestor::tr >> button[aria-label="Edit"]`);
  await staff.waitForSelector('[data-screen="CWP-072"]', { timeout: 20000 });
  const langs = await staff.locator("[data-variant]").evaluateAll((nodes) =>
    nodes.map((n) => [n.getAttribute("data-variant"), n.querySelector("[data-variant-status]")?.getAttribute("data-variant-status")]),
  );
  const byLocale = Object.fromEntries(langs);
  check(byLocale["en"] === "published", "English is published");
  check(byLocale["es-MX"] === "published", "Español (México) is published");
  check(byLocale["fr-FR"] === "needs_translating", "⚠ Français NEEDS TRANSLATING — visible, not hidden");
  check(byLocale["hi"] === "published", "हिन्दी is published");
  const editorText = await staff.locator("body").innerText();
  check(editorText.includes("Français"), "the table names each language in its own words");
  check(
    (await staff.locator("[data-publish-warning]").count()) === 1,
    "the screen warns that publishing is immediate",
  );
  check(
    editorText.includes("Nobody approves it first."),
    "…in those words: nobody approves it first",
  );
  // rule 6: Publish is not a destructive commit and must not wear the danger tier.
  const publishVariant = await staff.locator('[data-action="publish"]').getAttribute("data-variant");
  check(publishVariant !== "danger", `Publish is not the danger tier (${publishVariant})`);
  await staff.screenshot({ path: join(OUT, "2-answer-editor.png"), fullPage: true });

  // ═════ 3 · the guest list, and the French fallback ══════════════════════
  console.log("\n── 3 · six answers, and a French browser reads English and is told so ──");
  const guest = await context.newPage();
  await guest.goto(HELP, { waitUntil: "networkidle" });
  await guest.waitForSelector('[data-screen="CWP-011"]', { timeout: 20000 });
  const shown = await guest.locator("[data-answer]").evaluateAll((n) => n.map((e) => e.getAttribute("data-answer")));
  check(shown.length === 6, `six answers on the portal (${shown.length})`);
  check(shown[0] === BILL_HIGHER, "in the back office's order — the bill answer first");
  check(!shown.includes("when-is-my-meter-read"), "the draft is not there");
  check(!shown.includes("who-is-responsible-for-the-pipe-outside"), "the not-shown one is not there");
  const guestText = await guest.locator("body").innerText().then((t) => t.toLowerCase());
  for (const forbidden of ["hidden", "draft", "not shown", "of 8", "8 answers"]) {
    check(!guestText.includes(forbidden), `no count of what is hidden: "${forbidden}" is absent`);
  }
  const french = await context.newPage({ locale: "fr-FR" });
  await french.goto(`${HELP}/${BILL_HIGHER}`, { waitUntil: "networkidle" });
  await french.waitForSelector('[data-screen="CWP-060"]', { timeout: 20000 });
  const frenchBody = await french.locator("[data-answer-body]").innerText();
  check(frenchBody.startsWith("Most of the time"), "a French browser gets the ENGLISH answer");
  check(
    (await french.locator("[data-fallback-note]").count()) === 1,
    "…with a line saying which language it is in",
  );
  await french.screenshot({ path: join(OUT, "3-french-fallback.png"), fullPage: true });
  await french.close();
  await guest.screenshot({ path: join(OUT, "3-guest-help.png"), fullPage: true });

  // ═════ 4 · three reads and one No ═══════════════════════════════════════
  console.log("\n── 4 · three opens move it by three, and the vote is its own event ──");
  // ⚠ READ IT AGAIN HERE. Step 3 opened the answer once (the French visitor),
  // and that read is as real as these three — measuring from step 1 would
  // count it and report +4, which is the product being RIGHT and the check
  // being wrong.
  const beforeThree = Number(
    (await staff.request.get(`${BASE}/api/${TENANT}/settings/portal/help/${BILL_HIGHER}`).then((r) => r.json()))
      .reads_this_month,
  );
  for (let i = 0; i < 3; i += 1) {
    await guest.goto(`${HELP}/${BILL_HIGHER}`, { waitUntil: "networkidle" });
    await guest.waitForSelector("[data-answer-body]", { timeout: 20000 });
  }
  await guest.click('[data-vote="not_helpful"]');
  await guest.waitForSelector("[data-vote-thanks]", { timeout: 15000 });
  await staff.goto(HELP_SETTINGS, { waitUntil: "networkidle" });
  await staff.waitForSelector('[data-screen="CWP-071"]', { timeout: 20000 });
  const after = (await staff.locator(`[data-reads="${BILL_HIGHER}"]`).innerText()).trim();
  const readsAfter = Number(after.replace(/,/g, ""));
  check(
    readsAfter === beforeThree + 3,
    `the read count moved ${beforeThree.toLocaleString("en-US")} → ${after} — three opens, three reads`,
  );
  const votes = await staff.request.get(`${BASE}/api/${TENANT}/settings/portal/help/${BILL_HIGHER}`);
  const body = await votes.json();
  check(body.reads_this_month === readsAfter, `and the API agrees: ${body.reads_this_month} reads`);
  // ⚠ THE VOTE IS ITS OWN EVENT: pressing *No* did not move the read column.
  check(
    readsAfter - beforeThree === 3,
    "the No vote is counted separately — it moved the read column by nothing",
  );

  // ═════ 5 · tips ═════════════════════════════════════════════════════════
  console.log("\n── 5 · six tips, four showing, and one quiet for two reasons ──");
  await staff.goto(TIPS_SETTINGS, { waitUntil: "networkidle" });
  await staff.waitForSelector('[data-screen="CWP-073"]', { timeout: 20000 });
  check((await staff.locator("[data-tip-row]").count()) === 6, "six tips");
  check((await staff.locator('[data-showing="yes"]').count()) === 4, "four showing today");
  check((await staff.locator('[data-showing="no"]').count()) === 2, "two not — and neither is a fault");
  // The switch and the season note live in SIBLING cells, so the row is the
  // scope — a locator on the cell finds neither, and would pass by absence.
  const freeze = staff.locator('tr:has([data-tip-row="portal_home"])');
  check(
    (await freeze.locator('[data-switch-state="off"]').count()) === 1,
    "the freeze tip is OFF …",
  );
  check(
    (await freeze.locator("[data-out-of-season]").count()) === 1,
    "… AND out of season — two independent reasons",
  );
  await staff.screenshot({ path: join(OUT, "5-tips.png"), fullPage: true });

  // ═════ 6 · service centres ══════════════════════════════════════════════
  console.log("\n── 6 · three centres, and hidden is a state ──");
  await staff.goto(CENTRES_SETTINGS, { waitUntil: "networkidle" });
  await staff.waitForSelector('[data-screen="CWP-074"]', { timeout: 20000 });
  check((await staff.locator("[data-centre-row]").count()) === 3, "three centres in the back office");
  check(
    (await staff.locator('[data-centre-row="depot"][data-shown="no"]').count()) === 1,
    "the depot is HIDDEN and still in the list",
  );
  await staff.click('[data-centre-row="north-counter"] >> xpath=ancestor::tr >> button[aria-label="Edit"]');
  await staff.waitForSelector('[data-screen="CWP-075"]', { timeout: 20000 });
  // r10 rule 9 / B14 rule 36 breach (e): chips, never a wall of checkboxes.
  check(
    (await staff.locator('[data-chip-select="actions"]').count()) === 1,
    "what a customer can do here is CHIPS, not checkboxes",
  );
  check((await staff.locator('input[type="checkbox"]').count()) === 0, "…and there is no checkbox on the screen");
  check(
    (await staff.locator('[data-chip-select="methods"] [data-chip]').count()) === 2,
    "it takes cash and cheque — two chips, no card",
  );
  await staff.screenshot({ path: join(OUT, "6-centre-editor.png"), fullPage: true });

  // ═════ 7 · where you can walk in ════════════════════════════════════════
  console.log("\n── 7 · two centres, and the clock says when ──");
  await guest.goto(VISIT, { waitUntil: "networkidle" });
  await guest.waitForSelector('[data-screen="CWP-013"]', { timeout: 20000 });
  check((await guest.locator("[data-centre]").count()) === 2, "two centres on the portal");
  check((await guest.locator('[data-centre="depot"]').count()) === 0, "the depot is absent");
  const northLine = (await guest.locator('[data-centre-status="north-counter"]').innerText()).trim();
  check(
    northLine.includes("Closed today") && northLine.includes("Thursday") && northLine.includes("9:00am"),
    `the north counter reads "${northLine}"`,
  );
  check(!northLine.includes("Tuesday"), "⚠ not Tuesday — the drawing was wrong (DEF-CWP-3604)");
  const holiday = (await guest.locator("[data-next-holiday]").first().innerText()).trim();
  check(
    holiday.includes("26") && holiday.includes("Thanksgiving"),
    `the footer holiday, read from the calendar: "${holiday}"`,
  );
  await guest.screenshot({ path: join(OUT, "7-visit.png"), fullPage: true });
  await guest.goto(`${VISIT}/north-counter`, { waitUntil: "networkidle" });
  await guest.waitForSelector('[data-screen="CWP-014"]', { timeout: 20000 });
  check((await guest.locator('[data-can="no"]').count()) === 4, "four of the five action rows say no");
  check((await guest.locator('[data-can="yes"]').count()) === 1, "…and one says yes");
  check((await guest.locator('[data-method="card"]').count()) === 0, "no card machine, and the screen says so");
  await guest.screenshot({ path: join(OUT, "7-one-centre.png"), fullPage: true });

  // ═════ 9 · the utilities compiled ═══════════════════════════════════════
  console.log("\n── 9 · computed style: the rules actually exist, colour included ──");
  const centreStyle = await guest.locator("[data-panel]").first().evaluate((el) => {
    const s = getComputedStyle(el);
    return { border: s.borderTopStyle, width: s.borderTopWidth, bg: s.backgroundColor, pad: getComputedStyle(el.querySelector("div") ?? el).paddingTop };
  });
  check(centreStyle.border === "solid" && centreStyle.width === "1px", `a 1px rule around a panel (${centreStyle.width} ${centreStyle.border})`);
  check(centreStyle.bg === "rgb(255, 255, 255)", `bg-[white] compiled (${centreStyle.bg})`);
  const brand = await guest.locator('[data-portal-frame="guest"]').evaluate((el) => getComputedStyle(el).getPropertyValue("--brand").trim());
  check(brand.toLowerCase() === "#ec3013", `--brand is the tenant's own hex (${brand})`);
  // ⚠ A COLOUR read from computed style, which is what rule 36 asks for: a
  // token that did not compile is a class name in the DOM and nothing else.
  const chipColour = await staff.locator("[data-chip]").first().evaluate((el) => getComputedStyle(el).borderTopColor);
  check(chipColour !== "" && chipColour !== "rgba(0, 0, 0, 0)", `a chip's border colour compiled (${chipColour})`);

  // ═════ 10 · nothing internal, no sideways scroll, and the geometry ══════
  console.log("\n── 10 · nothing a person should not see, and nothing one word wide ──");
  for (const [name, page] of [["the portal", guest], ["the back office", staff]]) {
    const text = await page.locator("body").innerText();
    for (const pattern of FORBIDDEN) {
      const hit = text.match(pattern);
      check(hit === null, `no ${pattern} on ${name}${hit ? ` — found ${hit[0]}` : ""}`);
    }
    const sideways = await page.evaluate(SIDEWAYS);
    check(sideways === 0, `no sideways scroll on ${name} at ${VIEWPORT.width} (overflow ${sideways}px)`);
  }
  // ⚠ RULE 36's OWN FINDING: a column so narrow the text wraps one word per
  // line. No suite can see it — text content is identical however it wraps —
  // so it is measured: the tallest cell against its own line height.
  await staff.goto(HELP_SETTINGS, { waitUntil: "networkidle" });
  await staff.waitForSelector('[data-screen="CWP-071"]', { timeout: 20000 });
  //
  // ⚠ **THE FIRST DRAFT OF THIS CHECK COULD NOT FAIL CORRECTLY, AND THAT IS
  // WORTH THE PARAGRAPH.** It divided a cell's HEIGHT by its line-height —
  // but every cell in a row is as tall as the tallest one, so a long question
  // wrapping in its own column reported every cell beside it as "two lines",
  // including `10 of 11` in a 134px column that does not wrap at all. It
  // failed on a healthy screen, which is the same class of fault as a check
  // that passes on a broken one (DEF-182).
  //
  // The measurement is taken on the DEEPEST element that holds the text — the
  // leaf carries no padding and none of its neighbours' height, so its own
  // box divided by its own line-height is the number of lines that text
  // really occupies. (A `Range` over the cell was tried first and counts an
  // extra rect per element boundary, which is the same over-reporting one
  // level down.)
  const worst = await staff.locator("table td").evaluateAll((cells) => {
    let worstText = "";
    let worstLines = 0;
    for (const cell of cells) {
      let leaf = cell;
      while (leaf.children.length === 1 && (leaf.children[0].textContent ?? "").trim() === (leaf.textContent ?? "").trim()) {
        leaf = leaf.children[0];
      }
      const text = (leaf.textContent ?? "").trim();
      const words = text.split(/\s+/).filter(Boolean).length;
      if (words < 3) continue;
      const style = getComputedStyle(leaf);
      const line = parseFloat(style.lineHeight) || 20;
      const lines = Math.round(leaf.getBoundingClientRect().height / line);
      if (lines > 1 && words / lines < 2.2 && lines > worstLines) {
        worstLines = lines;
        worstText = `${words} words over ${lines} lines: "${text.slice(0, 60)}"`;
      }
    }
    return worstText;
  });
  check(worst === "", worst === "" ? "no cell wraps at fewer than two words a line" : `⚠ a column is too narrow — ${worst}`);

  // ═════ 8 · hide everything, and the links go with it ════════════════════
  console.log("\n── 8 · hide every centre and unpublish every answer: the links go ──");
  // ⚠ **THE STATE IS PUT BACK AT THE END OF THIS STEP, AND THE FIRST RUN THAT
  // DID NOT MADE THE SECOND ONE FAIL ON AN EMPTY PORTAL.** A walkthrough that
  // leaves the fixture changed is a walkthrough that can only be run once,
  // and its second failure looks exactly like a broken screen — the same trap
  // this file's own header warns about for a mid-run reseed.
  const centres = await staff.request.get(`${BASE}/api/${TENANT}/settings/reference-data/service-centres`);
  const wasShown = (await centres.json()).centres.map((c) => [c.slug, c.is_shown_to_customers]);
  const answers = await staff.request.get(`${BASE}/api/${TENANT}/settings/portal/help`);
  const wasStatus = (await answers.json()).answers.map((a) => [a.slug, a.status]);
  for (const [slug] of wasShown) {
    await staff.request.put(`${BASE}/api/${TENANT}/settings/reference-data/service-centres/${slug}`, {
      data: { is_shown_to_customers: false },
    });
  }
  for (const [slug] of wasStatus) {
    await staff.request.post(`${BASE}/api/${TENANT}/settings/portal/help/${slug}/publish`, {
      data: { status: "not_shown" },
    });
  }
  await guest.goto(`${BASE}/${TENANT}/portal`, { waitUntil: "networkidle" });
  await guest.waitForSelector('[data-portal-frame="guest"]', { timeout: 20000 });
  check((await guest.locator('[data-link="visit"]').count()) === 0, "the Visit us link is absent");
  check((await guest.locator('[data-link="help"]').count()) === 0, "the Help link is absent");
  // ⚠ **THIS ASKED FOR THE CARD TO BE ABSENT UNTIL 2026-09-05** — PO ruling
  // *"for completess have them on screen"*. The card is drawn now and says
  // why; the LINKS above it are still absent, which is the whole distinction:
  // a catalogue tells you what exists, a nav word takes you somewhere.
  check((await guest.locator('[data-errand="help_answers"]').count()) === 1, "the Help & answers card is drawn");
  const unpublished = await guest.locator('[data-errand="help_answers"]').innerText();
  check(
    /Nothing published here yet/i.test(unpublished),
    `and it says why, in the reader's own language: ${unpublished.replace(/\n/g, " ")}`,
  );
  check(
    (await guest.locator('[data-errand="help_answers"] a').count()) === 0,
    "and it links nowhere, so no door opens onto an empty list (BR-CWP-093)",
  );
  const visitAfter = await guest.request.get(`${BASE}/api/${TENANT}/portal/public/service-centres`);
  check(visitAfter.status() === 404, `and the visit page itself answers ${visitAfter.status()} — no empty page`);
  const helpAfter = await guest.request.get(`${BASE}/api/${TENANT}/portal/public/help`);
  check((await helpAfter.json()).answers.length === 0, "the help list is empty rather than partial");
  await guest.screenshot({ path: join(OUT, "8-nothing-published.png"), fullPage: true });
  // …and back, so the next run starts where this one did.
  for (const [slug, shown] of wasShown) {
    await staff.request.put(`${BASE}/api/${TENANT}/settings/reference-data/service-centres/${slug}`, {
      data: { is_shown_to_customers: shown },
    });
  }
  for (const [slug, status] of wasStatus) {
    await staff.request.post(`${BASE}/api/${TENANT}/settings/portal/help/${slug}/publish`, { data: { status } });
  }
  const restored = await staff.request.get(`${BASE}/api/${TENANT}/portal/public/help`);
  check(
    (await restored.json()).answers.length === 6,
    "the fixture is back where it started — six answers published again",
  );

  // ═════ 11 · measured, not asserted ═════════════════════════════════════
  console.log("\n── 11 · what it cost, measured (11-response-times.md) ──");
  await timings.report({
    targets: [
      { id: "RT-1", match: "/portal/public/help", p95: 400 },
      { id: "RT-1", match: "/portal/public/service-centres", p95: 400 },
    ],
  });

  await browser.close();
  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr068 wave D: an answer is published and read the same minute, and a hidden depot stays hidden");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
