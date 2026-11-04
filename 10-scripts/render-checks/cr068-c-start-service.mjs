/**
 * RENDERED-OUTPUT CHECK — CR-068 wave C, "Start service before identity
 * exists", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*. A story is not signed off
 * until this has run green against a running product.
 *
 * ⚠ **AND B14 RULE 21 MAKES IT UNAVOIDABLE HERE.** A Tailwind utility is
 * emitted only for a file the ledger owns AND only if the theme declares it —
 * this theme clears Tailwind's stock palette, so `bg-white` and `text-lg`
 * compile to NOTHING while tsc, eslint and every `toContain` pass (DEF-974).
 * The only thing that can prove wave C's rules compiled is computed style in a
 * real engine — step 9 below, which reads a COLOUR as well as a geometry.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cr068c --export)"   # sub-second
 *   DJANGO_SETTINGS_MODULE=config.settings.local python3 06-backend/manage.py migrate
 *   DJANGO_SETTINGS_MODULE=config.settings.local python3 06-backend/manage.py seed_portal_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8168 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4368 API_PROXY_TARGET=http://127.0.0.1:8168 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4368 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-c-start-service.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ⚠ **AND CLEAR THE THROTTLE'S CACHE FIRST, OR A SECOND RUN INSIDE ONE
 * MINUTE FAILS FOR A REASON THAT IS NOT A DEFECT.** The guest edge allows
 * sixty requests a minute from one address (`BR-CWP-022`) and this script
 * makes more than that across two runs; the saves are then turned away with
 * `429` and the form legitimately loses what was typed. That is the product
 * behaving correctly, and it looks exactly like a broken form:
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=… \
 *     python3 06-backend/manage.py shell -c \
 *       "from django.core.cache import cache; cache.clear()"
 *
 * ── WHAT IT CLICKS (the wave C demo script, 10-execution-plan.md) ─────────
 *   1  `/pine-hill/portal/start-service`, type `31 Palm Ct`, *Check →*. FOUR
 *      rows — Water YES $185.00 $150.00 · Sewer YES Included · Trash YES
 *      $0.00 · Electric NOT HERE greyed — and the IF YOU APPLY box reading
 *      $185.00 before we start and $150.00 on the first bill.
 *   2  An address matching no premises: *a person will look at it*, and the
 *      *Apply* route still open — never a refusal (US-CWP-012 TC-2).
 *   3  *Continue →* opens WHEN (step 2 of 4) — the start date and whether it
 *      is a home or a business — then *Continue →* again for ABOUT YOU
 *      (step 3 of 4), whose date-of-birth helper says why we ask and
 *      discloses nothing, and whose proof-of-identity box is HELD with no
 *      file input at all (consumer upload is a signed deferral, `DF-4`).
 *      ⚠ **STEP 2 AND STEP 3 WERE ONE SCREEN UNTIL `CR-085` TASK (c)**, so
 *      the step bar drew step 3 as ✓ done having never shown it. PO ruling:
 *      *"please show all 4 screens - address, when , about you, check"*.
 *   4  Close the tab, reopen the draft link: the fields are still there, NO
 *      reference has been issued (US-CWP-013 TC-1), and the screen says it
 *      picked up where the applicant left off (wireframe s19).
 *   5  Check and send (CWP-009): the KVList, the two AFTER YOU APPLY rows, the
 *      boxed consent with *we print them as well*, the four-bullet box. Send.
 *   6  A reference on screen; and in the DATABASE, through the API: one
 *      service request with channel `customer_portal`, one consent row with
 *      its wording version. No payment, no document, no account.
 *   7  Ask for a quick service (CWP-010): six cards from the tenant's own
 *      list; ask for a re-read and get a reference.
 *   8  Oak Ridge: its own three cards, one renamed, and NOT ONE Pine Hill
 *      string or figure.
 *   9  The utilities COMPILED, read as computed style — geometry AND a colour.
 *  10  Nothing internal on screen: no uuid, no rule id, no draft token; and no
 *      sideways scroll at 1440.
 *  11  MEASURED, NOT ASSERTED: every `/api/` round trip the browser made,
 *      through `lib/timings.mjs`, printed against RT-1 and RT-7 as figures
 *      rather than verdicts (11-response-times.md §5).
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4368";
const TENANT = "pine-hill";
const OTHER = "oak-ridge";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-c";
const VIEWPORT = { width: 1440, height: 1000 };
const START = `${BASE}/${TENANT}/portal/start-service`;

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

/** A date input wants `YYYY-MM-DD`; this is three weeks out, always a weekday. */
function startDate() {
  const day = new Date(Date.now() + 21 * 24 * 3600 * 1000);
  while (day.getDay() === 0 || day.getDay() === 6) day.setDate(day.getDate() + 1);
  return day.toISOString().slice(0, 10);
}

async function cellText(page, service, column) {
  return (
    await page.locator(`[data-row="${service}"] [data-cell="${column}"]`).innerText()
  ).trim();
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  // ⚠ MEASURED, NOT ASSERTED (11-response-times.md §5). Attached to the
  // CONTEXT, so every page it opens is counted and nothing is hand-listed.
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-c: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · 31 Palm Ct — the four rows and their figures ═══════════════════
  console.log("\n── 1 · can I get service at 31 Palm Ct ──");
  await page.goto(START, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-008"]', { timeout: 20000 });
  check(
    (await page.locator("body").getAttribute("data-screen-id")) === "CWP-008",
    "the screen carries its id: CWP-008 on <body>",
  );
  check(
    (await page.locator("[data-minitable]").count()) === 0,
    "nothing is drawn before the server has answered",
  );
  await page.fill("#availability-address", "31 Palm Ct");
  await page.click('[data-action="check"]');
  await page.waitForSelector("[data-minitable]", { timeout: 20000 });

  const rows = await page
    .locator("[data-minitable] tbody tr")
    .evaluateAll((list) => list.map((row) => row.getAttribute("data-row")));
  check(
    JSON.stringify(rows) === JSON.stringify(["water", "sewer", "trash", "electric"]),
    `four rows in the utility's own order: ${rows.join(" · ")}`,
  );
  const water = [
    await cellText(page, "water", "available"),
    await cellText(page, "water", "to_connect"),
    await cellText(page, "water", "deposit"),
  ];
  check(
    water[0] === "YES" && water[1] === "$185.00" && water[2] === "$150.00",
    `Water · ${water.join(" · ")}`,
  );
  const sewer = [
    await cellText(page, "sewer", "available"),
    await cellText(page, "sewer", "to_connect"),
  ];
  check(sewer[0] === "YES" && sewer[1] === "Included", `Sewer · ${sewer.join(" · ")}`);
  const trash = await cellText(page, "trash", "to_connect");
  // ⚠ TC-4's distinction, on screen: `$0.00` is a price the utility set, and
  // `—` is nothing to quote. A row reading `$0.00` where it should read `—`
  // tells a visitor a service is free when it is simply not there.
  check(trash === "$0.00", `Trash · ${trash} — a figure, because the utility priced it at zero`);
  const electric = [
    await cellText(page, "electric", "available"),
    await cellText(page, "electric", "to_connect"),
  ];
  check(
    electric[0] === "NOT HERE" && electric[1] === "—",
    `Electric · ${electric.join(" · ")} — never $0.00`,
  );
  check(
    (await page.locator('[data-row="electric"]').getAttribute("data-muted")) === "true",
    "the Electric row is greyed, as the wireframe draws it",
  );
  const consequence = await page.locator("[data-consequence]").innerText();
  check(consequence.includes("$185.00 before we start"), "IF YOU APPLY · $185.00 before we start");
  check(
    consequence.includes("$150.00 deposit on your first bill"),
    "IF YOU APPLY · $150.00 deposit on your first bill",
  );
  check(consequence.includes("About 3 working days"), "IF YOU APPLY · about three working days");
  // ⚠ HARD RULE 2 ON THE WIRE AS WELL AS ON SCREEN: four decimals stored, two
  // shown, and the two agree. A screen showing $185.00 over a stored 185.5000
  // would pass every assertion above.
  const availability = await page.request.get(
    `${BASE}/api/${TENANT}/portal/public/premises/availability?address=31%20Palm%20Ct`,
  );
  const availabilityBody = await availability.json();
  const waterRow = availabilityBody.rows.find((row) => row.service_code === "water");
  check(
    waterRow.to_connect.amount === "185.0000" && waterRow.to_connect.display === "$185.00",
    `stored ${waterRow.to_connect.amount}, displayed ${waterRow.to_connect.display}`,
  );
  check(
    waterRow.deposit.amount === "150.0000" && waterRow.deposit.display === "$150.00",
    `stored ${waterRow.deposit.amount}, displayed ${waterRow.deposit.display}`,
  );
  // BR-CWP-021, asserted ON THE RESPONSE BODY — the wave's exit test.
  const flat = JSON.stringify(availabilityBody);
  for (const forbidden of ["Alvarez", "Maria", "555-0134", "customer", "account", "occupier"]) {
    check(!flat.includes(forbidden), `availability names no ${forbidden}`);
  }
  await page.screenshot({ path: join(OUT, "1-availability.png"), fullPage: true });

  // ═════ 2 · an address we do not hold ═════════════════════════════════════
  console.log("\n── 2 · an unknown address is not a refusal ──");
  await page.fill("#availability-address", "77 Nowhere Ln");
  await page.click('[data-action="check"]');
  await page.waitForSelector('[data-availability="unmatched"]', { timeout: 20000 });
  const unmatched = await page.locator('[data-availability="unmatched"]').innerText();
  check(unmatched.includes("a person will look at it"), `it says: ${unmatched.trim()}`);
  check(
    (await page.locator('[data-action="apply"]').count()) === 1,
    "the Apply route is still open — never a refusal",
  );
  check(
    (await page.locator("[data-minitable]").count()) === 0,
    "and not an empty table either",
  );
  await page.screenshot({ path: join(OUT, "2-unknown-address.png"), fullPage: true });

  // ═════ 3 · About you ═════════════════════════════════════════════════════
  console.log("\n── 3 · about you, and what the screen says about recognition ──");
  await page.fill("#availability-address", "31 Palm Ct");
  await page.click('[data-action="check"]');
  await page.waitForSelector("[data-minitable]", { timeout: 20000 });
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 20000 });
  const draftUrl = page.url();
  check(
    (await page.locator("body").getAttribute("data-screen-id")) === "CWP-047",
    "the screen carries its id: CWP-047 on <body>",
  );
  check(
    (await page.locator('[data-stepper] [data-state="current"]').getAttribute("data-step")) === "2",
    "the stepper reads step 2 of 4 — WHEN",
  );
  check(
    (await page.locator('[data-field="requested_start"]').count()) === 1,
    "step 2 asks the start date",
  );
  check(
    (await page.locator('[data-field="first_name"]').count()) === 0,
    "and asks nothing about the person yet",
  );
  await page.fill("#requested_start", startDate());
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, "3-when.png"), fullPage: true });

  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-step="about"]', { timeout: 20000 });
  check(
    (await page.locator('[data-stepper] [data-state="current"]').getAttribute("data-step")) === "3",
    "the stepper reads step 3 of 4 — ABOUT YOU",
  );
  // ⚠ The drop zone was HELD under `DF-4` until 2026-10-01. The PO superseded
  // it for this request (`CR-158-BRC10`), so the box is the live drop zone —
  // and the held shape must be gone, or the screen says two things.
  check(
    (await page.locator('[data-photo-picker="held"]').count()) === 0,
    "the held proof-of-identity shape is gone (DF-4 superseded here, CR-158-BRC10)",
  );
  check(
    (await page.locator('[data-application-documents] input[type="file"]').count()) === 1,
    "and the drop zone has a real file input",
  );
  const helper = await page.locator('[data-field="date_of_birth"]').innerText();
  check(
    helper.includes("held an account with us before"),
    "the date-of-birth helper says why we ask",
  );
  // ⚠ AND SAYS NOTHING ABOUT WHAT WE FOUND (US-CWP-013 TC-2).
  for (const leak of ["already on file", "returning", "match", "Alvarez"]) {
    check(!(await page.locator("body").innerText()).includes(leak), `the screen never says "${leak}"`);
  }
  await page.fill("#first_name", "Daniel");
  await page.fill("#last_name", "Okafor");
  await page.fill("#email", "d.okafor@example.test");
  await page.fill("#phone", "(512) 555-7730");
  await page.fill("#date_of_birth", "1987-12-04");
  await page.locator("#date_of_birth").blur();
  await page.screenshot({ path: join(OUT, "3-about-you.png"), fullPage: true });

  // ═════ 4 · close the tab, reopen the link ═══════════════════════════════
  console.log("\n── 4 · closed tab, reopened link: saved from the first keystroke ──");
  await page.close();
  const reopened = await context.newPage();
  await reopened.goto(draftUrl, { waitUntil: "networkidle" });
  await reopened.waitForSelector("[data-stepper]", { timeout: 20000 });
  // ⚠ **WIREFRAME s19 — SOMEBODY WHO COMES BACK IS TOLD SO, AND IS PUT ON THE
  // STEP THEY DID NOT FINISH.** Everything was typed before the tab closed, so
  // the step with nothing left on it is the LAST one: *"Nothing left but the
  // ID: the page is the drop zone and one button. No form at all."*
  check(
    (await reopened.locator("body").innerText()).includes("Picked up where you left off"),
    "the reopened link says it picked up where they left off",
  );
  check(
    (await reopened.locator('[data-screen="CWP-009"]').count()) === 1,
    "and opens on the step with something still to do — here, Check",
  );
  check(
    (await reopened.locator("[data-reference]").count()) === 0,
    "and NO reference has been issued — nothing has been promised",
  );
  await reopened.screenshot({ path: join(OUT, "4-draft-reopened.png"), fullPage: true });

  // The Change link is the way back to the fields, and proves they survived.
  await reopened.click('[data-change="about"]');
  await reopened.waitForSelector('[data-step="about"]', { timeout: 20000 });
  check((await reopened.inputValue("#first_name")) === "Daniel", "first name survived");
  check((await reopened.inputValue("#last_name")) === "Okafor", "last name survived");
  check(
    (await reopened.inputValue("#email")) === "d.okafor@example.test",
    "email survived",
  );

  // ═════ 5 · Check and send ════════════════════════════════════════════════
  console.log("\n── 5 · check and send, where the consent is taken ──");
  await reopened.click('[data-action="continue"]');
  await reopened.waitForSelector('[data-screen="CWP-009"]', { timeout: 20000 });
  check(
    (await reopened.locator('[data-change="when"]').count()) === 1 &&
      (await reopened.locator('[data-change="about"]').count()) === 1,
    "each block on the check screen has its own Change link back to its step",
  );
  const review = await reopened.locator("body").innerText();
  check(review.includes("31 Palm Ct"), "the summary names the address");
  check(review.includes("Daniel Okafor"), "the summary names the applicant");
  // §7 — the figures RESTATE CWP-008's and must not be recomputed.
  check(
    (await reopened.locator('[data-kv="before_we_start"] dd').innerText()).trim() === "$185.00",
    "to pay before we start · $185.00, the same figure CWP-008 showed",
  );
  check(
    (await reopened.locator('[data-kv="on_first_bill"] dd').innerText()).trim() === "$150.00",
    "on your first bill · $150.00",
  );
  check(
    (await reopened.locator("[data-document]").count()) === 2,
    "two document rows, both marked AFTER YOU APPLY",
  );
  check(
    (await reopened.locator('[data-document="photo_id"]').innerText()).includes("AFTER YOU APPLY"),
    "Photo ID · AFTER YOU APPLY",
  );
  const consent = await reopened.locator("[data-consent-box]").innerText();
  check(consent.includes("Send my bills and letters by email"), "the consent box asks the question");
  // ⚠ CR-068 R4 · TC-3 — PRINT STAYS THE FLOOR, and the screen must say so.
  check(consent.includes("We print them as well"), "the helper says: we print them as well");
  const bullets = await reopened.locator("[data-consequence] li").allInnerTexts();
  check(bullets.length === 4, `the consequence box has four bullets (${bullets.length})`);
  check(
    bullets.some((one) => one.includes("Nothing is charged today")),
    "one of them: nothing is charged today",
  );
  check(
    bullets.some((one) => one.includes("two working days")),
    "one of them: we answer within two working days",
  );
  // r10 rule 6 — the danger tier is for destructive commits, and this is not one.
  check(
    (await reopened.locator('[data-action="send"]').getAttribute("data-variant")) === "primary",
    "Send my application is the primary tier, not the danger one",
  );
  await reopened.screenshot({ path: join(OUT, "5-check-and-send.png"), fullPage: true });
  await reopened.click('[data-action="send"]');
  // ⚠ **A FAILED SEND MUST SAY WHY.** Waiting on `[data-sent]` alone times out
  // with *"waiting for locator"* — true, and useless: the screen is showing the
  // refusal all along. So the wait races the two, and a refusal is REPORTED.
  await Promise.race([
    reopened.waitForSelector("[data-sent]", { timeout: 25000 }),
    reopened.waitForSelector("[data-send-error]", { timeout: 25000 }),
  ]).catch(() => undefined);
  if ((await reopened.locator("[data-send-error]").count()) > 0) {
    check(false, `the send was refused: ${(await reopened.locator("[data-send-error]").innerText()).trim()}`);
  }
  await reopened.waitForSelector("[data-sent]", { timeout: 20000 });

  // ═════ 6 · the reference, and what is in the database ════════════════════
  console.log("\n── 6 · one request, one consent, and nothing else ──");
  const reference = (await reopened.locator("[data-reference]").innerText()).trim();
  check(/^SR-\d{2}-\d+$/.test(reference), `a reference on screen: ${reference}`);
  const draftToken = draftUrl.split("/").pop().split("?")[0];
  const afterSubmit = await (
    await reopened.request.get(`${BASE}/api/${TENANT}/portal/public/applications/${draftToken}`)
  ).json();
  check(afterSubmit.submitted === true, "the draft records that it was sent");
  check(afterSubmit.reference === reference, "and carries the same reference the screen shows");
  // ⚠ THE IDENTIFIER USED FOR RECOGNITION IS GONE (see services._application).
  check(afterSubmit.date_of_birth === null, "the date of birth was used and then cleared");
  await reopened.screenshot({ path: join(OUT, "6-sent.png"), fullPage: true });

  // ═════ 7 · the quick asks ════════════════════════════════════════════════
  console.log("\n── 7 · ask for a quick service ──");
  const ask = await context.newPage();
  await ask.goto(`${BASE}/${TENANT}/portal/ask`, { waitUntil: "networkidle" });
  await ask.waitForSelector("[data-errand]", { timeout: 20000 });
  const cards = await ask
    .locator("[data-errand]")
    .evaluateAll((list) => list.map((one) => one.getAttribute("data-errand")));
  check(cards.length === 6, `six cards from the tenant's own list (${cards.length})`);
  // ⚠ **READ THE CARD'S COMPUTED STYLE HERE, WHILE THE CARDS ARE ON SCREEN.**
  // Step 9 used to read it, and by then this page has been sent and shows the
  // confirmation instead — so the card was gone, `getComputedStyle` had nothing
  // to measure, and the check reported `null` rather than a colour or a
  // geometry. B14 rule 21 is the reason it matters at all: a utility that
  // compiled to nothing looks exactly like a card that is not there.
  const errandDisplay = await ask.evaluate(() => {
    const el = document.querySelector("[data-errand] article, [data-errand]");
    return el === null ? null : getComputedStyle(el).display;
  });
  check(
    (await ask.locator("body").innerText()).includes("needs you to sign in or ring us"),
    "the closing note draws the boundary",
  );
  await ask.click('[data-action="ask-re_read"]');
  await ask.waitForSelector('[data-asking="re_read"]', { timeout: 20000 });
  await ask.fill("#quick-name", "Daniel Okafor");
  await ask.fill("#quick-phone", "(512) 555-7730");
  await ask.fill("#quick-address", "1408 Elm St");
  await ask.click('[data-action="send-ask"]');
  await ask.waitForSelector("[data-asked]", { timeout: 20000 });
  const askReference = (await ask.locator("[data-reference]").innerText()).trim();
  check(/^SR-\d{2}-\d+$/.test(askReference), `a reference for the ask: ${askReference}`);
  await ask.screenshot({ path: join(OUT, "7-quick-service.png"), fullPage: true });

  // ═════ 8 · the other utility carries nothing of this one ═════════════════
  console.log("\n── 8 · Oak Ridge: its own words, its own list ──");
  const oak = await context.newPage();
  await oak.goto(`${BASE}/${OTHER}/portal/ask`, { waitUntil: "networkidle" });
  await oak.waitForSelector("[data-errand]", { timeout: 20000 });
  const oakCards = await oak
    .locator("[data-errand]")
    .evaluateAll((list) => list.map((one) => one.getAttribute("data-errand")));
  check(oakCards.length === 3, `Oak Ridge offers its own three cards (${oakCards.length})`);
  check(oakCards.includes("standpipe_permit"), "including one Pine Hill does not sell");
  const oakText = await oak.locator("body").innerText();
  check(oakText.includes("Check my meter reading"), "and its own words for the re-read card");
  for (const leak of ["Pine Hill", "$185.00", "$150.00", "Palm Ct"]) {
    check(!oakText.includes(leak), `no Pine Hill string on Oak Ridge: "${leak}"`);
  }
  const oakAvailability = await (
    await oak.request.get(
      `${BASE}/api/${OTHER}/portal/public/premises/availability?address=31%20Palm%20Ct`,
    )
  ).json();
  check(
    oakAvailability.matched === false && !JSON.stringify(oakAvailability).includes("185"),
    "and 31 Palm Ct on Oak Ridge quotes none of Pine Hill's fees",
  );
  await oak.screenshot({ path: join(OUT, "8-oak-ridge.png"), fullPage: true });

  // ═════ 9 · the utilities compiled ════════════════════════════════════════
  console.log("\n── 9 · computed style: the rules actually exist ──");
  const table = await ask.evaluate(() => null);
  const style = await reopened.locator("[data-consequence]").evaluate((el) => {
    const css = getComputedStyle(el);
    return {
      borderLeft: css.borderLeftWidth,
      borderLeftColor: css.borderLeftColor,
      background: css.backgroundColor,
      padding: css.paddingTop,
    };
  });
  check(style.borderLeft === "4px", `the consequence box's brand rule compiled (${style.borderLeft})`);
  // ⚠ A COLOUR, NOT ONLY A GEOMETRY. `border-l-[var(--brand)]` is the class
  // most likely to compile to nothing and look deliberate: a 4px rule in the
  // default ink is indistinguishable from a 4px rule in the brand at a glance.
  check(
    style.borderLeftColor === "rgb(236, 48, 19)",
    `and it is the tenant's own hex, read back as computed style (${style.borderLeftColor})`,
  );
  check(style.background === "rgb(255, 255, 255)", `bg-[white] compiled (${style.background})`);
  check(style.padding === "16px", `p-4 compiled (${style.padding})`);
  check(errandDisplay === "flex", `an errand card is display:flex (${errandDisplay})`);
  const tableType = await reopened.evaluate(() => null);
  // ⚠ **THIS READ `--brand` AND HAD BEEN RED FOR THREE DAYS (found 2026-09-08,
  // `CR-085` task (c)).** The check was written 2026-09-04 (`c9fe338a`);
  // `DEF-CWP-3736` landed the next day and DELETED `--brand` on purpose,
  // because the kit's controls compile to `var(--color-accent)` and a variable
  // no `var()` reads paints nothing. So the frame publishes `--color-accent`
  // and this asked for a name the product had renamed — hard-won law 7's
  // *looking at the wrong thing*, and it reported the failure honestly in a run
  // where a failure is easy to skim past. Read back live at 2026-09-08:
  // `--color-accent: #0B6E4F` on Oak Ridge's frame, `--brand` empty.
  const brand = await oak
    .locator('[data-portal-frame="guest"]')
    .evaluate((el) => getComputedStyle(el).getPropertyValue("--color-accent").trim());
  check(brand.toLowerCase() === "#0b6e4f", `Oak Ridge's own brand colour (${brand})`);
  void table;
  void tableType;

  // ═════ 10 · nothing internal, no sideways scroll ═════════════════════════
  console.log("\n── 10 · nothing a person should not see ──");
  for (const [name, target] of [
    ["check and send", reopened],
    ["quick service", ask],
    ["oak ridge", oak],
  ]) {
    const text = await target.locator("body").innerText();
    for (const pattern of FORBIDDEN) {
      const hit = text.match(pattern);
      check(hit === null, `no ${pattern} on ${name}${hit ? ` — found ${hit[0]}` : ""}`);
    }
    const sideways = await target.evaluate(SIDEWAYS);
    check(sideways === 0, `no sideways scroll on ${name} at ${VIEWPORT.width} (overflow ${sideways}px)`);
  }
  // ⚠ AND THE DRAFT TOKEN IS NOT A REFERENCE AND IS NEVER SHOWN AS ONE.
  check(
    !(await reopened.locator("body").innerText()).includes(draftToken),
    "the draft token stays in the address bar and never on the page",
  );

  // ═════ 11 · measured, not asserted ══════════════════════════════════════
  console.log("\n── 11 · what it cost, measured ──");
  await timings.report({
    title: "cr068-c · every /api round trip the browser made",
    targets: [
      // 11-response-times.md RT-1 (the guest lookup a stranger can aim traffic
      // at) and RT-7 (a write and an acknowledgement). Printed as MEASURED
      // figures against the target; the instrument cannot fail a run on one,
      // deliberately, and neither does this script.
      { id: "RT-1", match: "premises/availability", p95: 400 },
      { id: "RT-7", match: "applications", p95: 800 },
    ],
  });

  await browser.close();
  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const one of failures) console.log(`   · ${one}`);
    process.exit(1);
  }
  console.log("\n✓ cr068 wave C: somebody with no account can find out what they can get, and ask for it");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
