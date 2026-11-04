// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave D — the request queue, the import and the
//          two wizards with no step rail.
//          Screens: 16 `S83` requests list · 17 `S84` request detail ·
//          15 `S68`/`S81` the Imports tab · 13 `S23` change plan ·
//          14 `S24` payment plan.
// Defects: DEF-CUS-5009 · DEF-CUS-5010 · DEF-CUS-5011 · DEF-CUS-5071
// Rules:   B14 rule 3 (the numbered step rail on any flow with 2+ stages) ·
//          B14 rule 12 (All is the default chip) · B14 rule 32 (no internal
//          code in clerk-facing copy) · B14 rule 39 (the spacing scale) ·
//          B14 rule 40 (the page-head title is 32px) · BR-SHL-025
// Tests:   this file, run before and after every fix
// ───────────────────────────────────────────────────────
//
// WHY A WALKTHROUGH. Every one of wave D's four faults is invisible to the
// whole test suite, and three of them were invisible to a source grep too:
//
//   · a dotted i18n key printed as the reason a control is greyed out — it is
//     built server-side as an f-string, so no front-end search finds it and
//     `G32`'s message_key resolution cannot see it either;
//   · a row action chosen by a run STATUS while the clerk reads the run's
//     REJECTED count;
//   · a filter chip reading `All` over a request for `segment=open` — two
//     defaults, each correct, that nothing ever compared;
//   · a step rail declared in a constant and rendered by nothing.
//
// `renderToStaticMarkup` can reach the last three with the right assertion and
// reached none of them before this wave. The first needs the running product,
// because the key only exists once a real resolver has run on real premises.
//
// IT MEASURES RATHER THAN DESCRIBES, and it asserts. Every check below either
// prints a reading or fails with what it wanted — a walkthrough whose output a
// reader cannot grade is worse than none (CLAUDE.md law 7).
//
// USAGE
//     BASE=http://127.0.0.1:8651 \
//     CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//     node 10-scripts/cr094_wave_d_walkthrough.mjs
//
// ⚠ CHROMIUM_PATH IS NOT OPTIONAL ON THIS IMAGE. `playwright-core` resolves a
// build number from its own version and asks for
// `/opt/pw-browsers/chromium_headless_shell-1234/...`, which is absent; what
// IS installed is `chromium-1194`.
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8651";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
/** A-10432, balance 247.30, holds its unit — the change-plan door is live. */
const ACCOUNT = process.env.ACCOUNT ?? "01a09540-727d-7b81-a750-49ddd2e237be";
/**
 * AC-2026-00011, carrying a LIVE payment plan — so `can_propose` is false and
 * this screen correctly draws NO wizard at all.
 *
 * ⚠ **THE FIRST DRAFT OF THIS FILE CHECKED THE PAYMENT-PLAN RAIL HERE AND
 * FAILED, CORRECTLY.** `BR-CUS-043` allows exactly one live plan, so the
 * server answers *"this account already has a live payment plan"* and the
 * screen renders that sentence instead of three steps. A rail there would be
 * the defect, not the fix. Both cases are asserted below — the rail where a
 * plan CAN be proposed, and the reason where it cannot — because a check that
 * only ever looks at the happy account cannot tell a working screen from one
 * that draws a wizard over a refusal.
 */
const PLAN_ACCOUNT = process.env.PLAN_ACCOUNT ?? "01a09540-62ab-739a-80f8-ca558b2d4f26";
/** SR-26-0006 — served & vacant, so three of the five outcomes are refused. */
const SR_VACANT = process.env.SR_VACANT ?? "01a09540-793e-7c76-bf8a-b82578af3012";
/** SR-26-0004 — no premise record, which is the other lookup sentence. */
const SR_NO_PREMISE = process.env.SR_NO_PREMISE ?? "01a09540-789a-75aa-8c55-531e3b6746c7";
const OUT = process.env.OUT ?? "/tmp/cr094-wave-d";
mkdirSync(OUT, { recursive: true });

const results = [];
const failures = [];
function record(id, what, got) {
  results.push({ id, what, got });
  console.log(`\n[${id}] ${what}\n${typeof got === "string" ? got : JSON.stringify(got, null, 2)}`);
}
function check(id, what, ok, got) {
  results.push({ id, what, ok, got });
  if (!ok) failures.push(`${id} — ${what}`);
  console.log(`${ok ? "PASS" : "FAIL"}  [${id}] ${what}\n        ${JSON.stringify(got)}`);
}

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? undefined,
  args: ["--no-sandbox", "--ignore-certificate-errors"],
});

for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 950 } });
  const apiCalls = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) apiCalls.push(r.url());
  });
  page.on("console", (m) => {
    if (m.type() === "error") console.log("  console.error:", m.text().slice(0, 180));
  });
  const shot = (n) => page.screenshot({ path: `${OUT}/${width}-${n}.png`, fullPage: true });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("signin"), { timeout: 30000 });
  record(`00@${width}`, "signed in, landed on", page.url());

  // ── DEF-CUS-5071 · the rail both wizards did not draw ───────────────────
  for (const [name, url, words] of [
    ["change-plan", `${BASE}/${TENANT}/accounts/${ACCOUNT}/change-plan`, ["Plan", "Effective", "Confirm"]],
    // `A-10432` holds no plan, so the wizard is offered. See PLAN_ACCOUNT.
    ["payment-plan", `${BASE}/${TENANT}/accounts/${ACCOUNT}/payment-plan`, ["Terms", "Schedule", "Agreement"]],
  ]) {
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForTimeout(1300);
    const got = await page.evaluate(() => {
      const rail = document.querySelector('[data-wizard="rail"]');
      const steps = rail ? [...rail.querySelectorAll("[data-wizard-step]")] : [];
      const h1 = document.querySelector("h1");
      const first = steps[0];
      const badge = first?.querySelector("span[aria-hidden]");
      return {
        railPresent: rail !== null,
        railLabels: steps.map((b) => b.textContent.trim()),
        states: steps.map((b) => b.getAttribute("data-state")),
        // B14 rule 39 — the rail's own anchors, measured rather than read off
        // a stylesheet: `rail margin-bottom 24 · step 16×20 gap 12`.
        railMarginBottom: rail ? getComputedStyle(rail).marginBottom : null,
        stepPadding: first ? `${getComputedStyle(first).paddingTop} ${getComputedStyle(first).paddingLeft}` : null,
        stepGap: first ? getComputedStyle(first).columnGap : null,
        badgeSize: badge ? `${getComputedStyle(badge).width}×${getComputedStyle(badge).height}` : null,
        // B14 rule 40 — 32px page-head title, on every screen.
        h1: h1 ? h1.textContent.trim() : null,
        h1FontSize: h1 ? getComputedStyle(h1).fontSize : null,
        stepOfSentence:
          [...document.querySelectorAll("p")]
            .map((el) => el.textContent?.trim() ?? "")
            .find((text) => /^Step \d+ of \d+$/.test(text)) ?? null,
      };
    });
    check(`5071-${name}@${width}`, `${name} draws the shared rail with its three named steps`,
      got.railPresent && words.every((w) => got.railLabels.some((l) => l.includes(w))) &&
        got.states[0] === "active" && got.states[2] === "upcoming", got);
    check(`5071-${name}-rule39@${width}`, `${name} rail spacing is B14 rule 39's (24 below, 16×20 step, gap 12, badge 26)`,
      got.railMarginBottom === "24px" && got.stepPadding === "16px 20px" &&
        got.stepGap === "12px" && got.badgeSize === "26px×26px", {
        railMarginBottom: got.railMarginBottom, stepPadding: got.stepPadding,
        stepGap: got.stepGap, badgeSize: got.badgeSize,
      });
    check(`5071-${name}-rule40@${width}`, `${name} page-head title is 32px`,
      got.h1FontSize === "32px", { h1: got.h1, size: got.h1FontSize });
    await shot(`5071-${name}`);
  }

  // ── DEF-CUS-5071 · THE RAIL MUST MOVE, NOT JUST EXIST ───────────────────
  // A rail that draws three words and never changes is the same defect
  // wearing a rail, and the step-1 audit could not tell "the rail appears
  // after the first choice" from "the drawing is wrong" without walking it.
  // So this walks it: pick a plan, press Continue, read the states again.
  await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}/change-plan`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1300);
  // ⚠ **REAL GESTURES, NOT `element.click()` INSIDE `page.evaluate`.** The
  // first draft clicked the radio from inside the page and the rail did not
  // move: React's controlled `checked` did not take, so `planId` stayed empty,
  // `step1Reason` stayed *"pick a plan"* and Continue was refused — a FAILING
  // check over a screen that works. Playwright's own click dispatches a
  // trusted event, which is what a clerk's finger does.
  // ⚠ **THE LABEL, NOT THE INPUT.** `FormModal.css` hides the real radio and
  // draws `.dot` in its place, so Playwright refuses to click the input —
  // *"element is not visible"*, 58 retries and a timeout. A clerk clicks the
  // label, and so does this.
  const pickId = await page.evaluate(() => {
    const radio = [...document.querySelectorAll('input[name="rate_plan_id"]')].find(
      (r) => !r.disabled && !r.checked,
    );
    return radio ? radio.id : null;
  });
  check(`5071-pickable@${width}`, "at least one plan is offered on step 1", pickId !== null, pickId);
  await page.click(`label[for="${pickId}"]`);
  await page.waitForTimeout(400);
  await page.click(`button:has-text("Continue")`);
  await page.waitForTimeout(700);

  // ⚠ **THIS FOUND MORE THAN IT WAS WRITTEN FOR.** The first plan on offer
  // DROPS A SERVICE, so the frame refused the press with the flow's own
  // sentence — *"Confirm that the customer knows the service will end."* —
  // rather than advancing. That is `BR-CUS-041` and `B14` rule 11 working, and
  // `DEF-936`'s per-step channel carrying the reason to the button that
  // refused it. So it is asserted rather than worked around.
  const refusedFirst = await page.evaluate(() => ({
    blocked: document.querySelector('[data-wizard="blocked"]')?.textContent?.trim() ?? null,
    states: [...document.querySelectorAll("[data-wizard-step]")].map((b) => b.getAttribute("data-state")),
    ackOffered: document.getElementById("drop_ack") !== null,
  }));
  if (refusedFirst.blocked !== null) {
    check(`5071-refuses@${width}`, "a service-dropping plan REFUSES at the button with its own sentence, and the rail does not move",
      refusedFirst.states[0] === "active" && refusedFirst.ackOffered &&
        !refusedFirst.blocked.includes("customers."), refusedFirst);
    // …then acknowledge it, the way a clerk would, and go on.
    await page.click('label[for="drop_ack"]');
    await page.waitForTimeout(300);
    await page.click(`button:has-text("Continue")`);
    await page.waitForTimeout(700);
  }

  const advanced = await page.evaluate(() => {
    const steps = [...document.querySelectorAll("[data-wizard-step]")];
    // ⚠ **READ THE SENTENCE'S OWN ELEMENT, NOT `body.textContent`.** Scraping
    // the body matched `Step 1 of 3` running straight into the rail's first
    // badge and reported **"Step 1 of 31"** — a measurement artefact that reads
    // exactly like a product fault.
    const sentence = [...document.querySelectorAll("p")]
      .map((el) => el.textContent?.trim() ?? "")
      .find((text) => /^Step \d+ of \d+$/.test(text));
    return {
      states: steps.map((b) => b.getAttribute("data-state")),
      stepOfSentence: sentence ?? null,
      // BR-SHL-018: a COMPLETED step navigates (back); an upcoming one does not.
      step1Clickable: steps[0] ? !steps[0].disabled : null,
      step3Clickable: steps[2] ? !steps[2].disabled : null,
      blocked: document.querySelector('[data-wizard="blocked"]')?.textContent?.trim() ?? null,
    };
  });
  check(`5071-advances@${width}`, "picking a plan and pressing Continue moves the rail to step 2, and step 1 becomes navigable",
    advanced.states?.[0] === "done" && advanced.states?.[1] === "active" &&
      advanced.stepOfSentence === "Step 2 of 3" &&
      advanced.step1Clickable === true && advanced.step3Clickable === false, advanced);
  await shot("5071-change-plan-step2");

  // ── DEF-CUS-5071's other half · no wizard where none may be proposed ────
  // BR-CUS-043: one live plan per account. The rail must be ABSENT here and
  // the server's own sentence must be on screen — a rail over a refusal is
  // the mirror of the defect this wave fixed.
  await page.goto(`${BASE}/${TENANT}/accounts/${PLAN_ACCOUNT}/payment-plan`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1300);
  const blockedPlan = await page.evaluate(() => {
    const body = (document.body.textContent ?? "").replace(/\s+/g, " ");
    return {
      railPresent: document.querySelector('[data-wizard="rail"]') !== null,
      saysWhy: /already has a live payment plan/i.test(body),
      note: document.querySelector('[data-testid="cannot-propose"]')?.textContent?.trim() ?? null,
    };
  });
  check(`5071-blocked@${width}`, "an account that already has a plan gets the REASON and no rail",
    !blockedPlan.railPresent && blockedPlan.saysWhy, blockedPlan);
  await shot("5071-payment-plan-blocked");

  // ── DEF-CUS-5009 · which run is offered which action ────────────────────
  await page.goto(`${BASE}/${TENANT}/accounts?tab=imports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  const imports = await page.evaluate(() => {
    return [...document.querySelectorAll("tbody tr")].map((tr) => {
      const cells = [...tr.querySelectorAll("td")].map((td) => td.textContent.trim());
      return {
        run: cells[0],
        rejected: cells[6],
        status: cells[7],
        actions: [...tr.querySelectorAll("button")].map((b) => ({
          label: (b.getAttribute("aria-label") ?? "").trim(),
          disabled: b.disabled === true,
          reason: b.getAttribute("title") ?? "",
        })).filter((a) => a.label.length > 0),
      };
    });
  });
  record(`5009-rows@${width}`, "Imports tab — every run, its rejected count and the actions offered", imports);
  const withRejects = imports.filter((r) => Number(r.rejected.replace(/,/g, "")) > 0);
  const withoutRejects = imports.filter((r) => Number(r.rejected.replace(/,/g, "")) === 0);
  check(`5009-a@${width}`, "every run WITH rejected rows is offered the fix",
    withRejects.length > 0 && withRejects.every((r) => r.actions.some((a) => /fix/i.test(a.label))),
    withRejects.map((r) => ({ run: r.run, rejected: r.rejected, actions: r.actions.map((a) => a.label) })));
  check(`5009-b@${width}`, "no run WITHOUT rejected rows is offered a fix for rows it has not got",
    withoutRejects.every((r) => !r.actions.some((a) => /fix/i.test(a.label))),
    withoutRejects.map((r) => ({ run: r.run, rejected: r.rejected, actions: r.actions.map((a) => a.label) })));
  // ⏳ ACC-S9's hold, asserted so this walkthrough goes RED the day it is built.
  const heldFix = imports.flatMap((r) => r.actions).find((a) => /fix/i.test(a.label));
  check(`5009-hold@${width}`, "ACC-S9 · the fix is still HELD and still says why (this FAILS when it is built)",
    heldFix !== undefined && heldFix.disabled && heldFix.reason.length > 0, heldFix ?? null);
  await shot("5009-imports");

  // ── DEF-CUS-5011 · the chip and the query string, together ──────────────
  apiCalls.length = 0;
  await page.goto(`${BASE}/${TENANT}/requests`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  const chips = await page.evaluate(() => {
    const row = document.querySelector("[data-chip-row]");
    return {
      chips: [...(row?.querySelectorAll("[data-chip]") ?? [])].map((c) => ({
        text: c.textContent.replace(/\s*×\s*$/, "").trim(),
        pressed: c.getAttribute("aria-pressed"),
      })),
      footer: (document.body.textContent ?? "").match(/1[–-]\d+ of \d+/)?.[0] ?? null,
      rows: document.querySelectorAll("tbody tr").length,
    };
  });
  const asked = apiCalls.filter((u) => u.includes("service-requests?"));
  check(`5011@${width}`, "the requests list says on screen exactly what it asks the server for",
    chips.chips.some((c) => /Open/.test(c.text)) &&
      chips.chips.every((c) => c.pressed !== "true" || !/^All$/.test(c.text)) &&
      asked.length > 0 && asked.every((u) => u.includes("segment=open")),
    { chips: chips.chips, footer: chips.footer, rows: chips.rows, asked });
  await shot("5011-requests");

  // ── DEF-CUS-5010 · what a clerk reads as the reason a control is refused ─
  for (const [name, id] of [["served-vacant", SR_VACANT], ["no-premise", SR_NO_PREMISE]]) {
    await page.goto(`${BASE}/${TENANT}/requests/${id}?tab=decision`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.evaluate(() => {
      const tab = [...document.querySelectorAll('[role="tab"], button, a')]
        .find((el) => /^decision$/i.test((el.textContent ?? "").trim()));
      if (tab) tab.click();
    });
    await page.waitForTimeout(1100);
    const got = await page.evaluate(() => {
      const body = (document.body.textContent ?? "").replace(/\s+/g, " ");
      return {
        dottedKeys: [...new Set(body.match(/customers\.[A-Za-z.]+/g) ?? [])],
        refusals: [...document.querySelectorAll("[data-outcome]")].map((b) => ({
          outcome: b.getAttribute("data-outcome"),
          verdict: b.getAttribute("data-verdict"),
          disabled: b.disabled === true,
          reason: b.getAttribute("title") ?? "",
        })),
      };
    });
    check(`5010-${name}@${width}`, `the Decision tab prints no dotted key, and every refused control carries WORDS`,
      got.dottedKeys.length === 0 &&
        got.refusals.filter((r) => r.verdict === "not_possible")
          .every((r) => r.disabled && r.reason.length > 0 && !r.reason.includes("customers.")),
      got);
    await shot(`5010-${name}`);
  }
  await page.close();
}

writeFileSync(`${OUT}/measurements.json`, JSON.stringify({ results, failures }, null, 2));
console.log(`\n\n${results.length} readings written to ${OUT}/measurements.json`);
if (failures.length > 0) {
  console.log(`\n${failures.length} CHECK(S) FAILED:\n  ${failures.join("\n  ")}`);
  process.exitCode = 1;
} else {
  console.log("\nevery check passed at 1280 and 1440");
}
await browser.close();
