/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-110-BRC04 phase 2 — the `they_hold_ours` SHAPE fixed on all six
 *          connectors (DEF-INT-5531..5538).
 * Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
 *          output) · law 7 habit 3 (a check's output must tell pass from fail
 *          to a READER) · B14 rule 42 (built from the drawing AS AN IMAGE —
 *          p062, p064, p065, p066).
 * ───────────────────────────────────────────────────────
 *
 * THE PO's OWN ELEVEN-STEP CLERK JOURNEY, WALKED END TO END — and walked on
 * TWO connectors, because every rule this wave fixed is a rule about a SHAPE
 * and one connector cannot prove a shape:
 *
 *     erp_workday      `out · them` — a finance system READS from us
 *     payments_kiosk   `in  · them` — a kiosk SENDS payments to us
 *
 * The kiosk is the one that matters: it is the only connector in the
 * issue-a-key set that is genuinely `in · them`, so it is the case where a fix
 * mapping `initiative === "them"` to a single phrase is STILL wrong after the
 * change. That is exactly how the direction words came to be wrong for four
 * quadrants in the first place.
 *
 *     1  Settings → Connectors
 *     2  the grid, a category chip narrows it
 *     3  the card, press Connect
 *     4  choose Production or Sandbox        ← both, not one of two
 *     5  type the allowed addresses
 *     6  switch each API on or off
 *     7  press Generate a key
 *     8  copy the key — shown once, never again
 *     9  press Save and test → activates
 *    10  hand the key over, outside the product
 *    11  watch "Who has been reading"
 *
 * ⚠ **STEPS 7 AND 9 ARE WALKED IN THE ORDER THE PRODUCT SUPPORTS AND THE
 * DIFFERENCE IS REPORTED RATHER THAN HIDDEN.** A key belongs to a CONNECTION
 * and there is no connection row until Save, so today the product is 9-then-7.
 * This script prints which order it walked; it does not quietly build one and
 * report the other.
 *
 * RUN IT:
 *     (cd 07-frontend && ./node_modules/.bin/vite build)
 *     STATIC_DIR=$PWD/07-frontend/dist API_PROXY_TARGET=http://127.0.0.1:<api> \
 *       PORT=<port> node 07-frontend/server.mjs
 *     node 10-scripts/cr110_they_hold_ours_clerk_walk.mjs
 *
 * ⚠ **CHECK THE SERVED BUNDLE IS YOURS.** The first measurement of this wave
 * was taken against a stack at 2.283.1 — two of the faults had already moved —
 * and only `curl <base>/ | grep assets/index-` said so.
 */
import { createRequire } from "node:module";
const require = createRequire("file:///home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8512";
const T = "brazosbend";
const OUT = process.env.OUT || "/tmp/claude-0/-home-user-SMARTBillHub/d8cc0edb-6533-58a7-9b8e-548fbd3d8b79/scratchpad/laneAcl/shots";

let fails = 0;
const say = (label, ok, detail = "") => {
  console.log(`  ${ok ? "OK" : "XX"} ${label}${detail ? " — " + detail : ""}`);
  if (!ok) fails++;
};

const bundle = (await (await fetch(BASE + "/")).text()).match(/assets\/index-[^"]*\.js/)?.[0];
console.log(`served bundle: ${bundle}`);

const b = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--no-sandbox"],
});
const p = await b.newPage({ viewport: { width: 1440, height: 1400 } });
const errs = [];
p.on("pageerror", (e) => errs.push(String(e).slice(0, 200)));
p.on("response", (r) => {
  if (r.status() >= 400 && r.url().includes("/api/")) errs.push(`${r.status()} ${r.url().split("/api/")[1]}`);
});

await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
await p.fill("#signin-email", "dana@brazosbendutilities.com");
await p.fill("#signin-password", "S3cure!passw0rd");
await p.click('button[type="submit"]');
await p.waitForTimeout(2500);

/** ⚠ THE ERROR BOUNDARY SWALLOWS A CRASH, so `pageerror` stays EMPTY while the
 *  page reads *Unexpected Application Error*. A fixture that cannot tell a
 *  crashed screen from a working one is law 7's "looking at the wrong thing". */
async function alive(where) {
  const crashed = await p.locator("text=Unexpected Application Error").count();
  say(`${where}: the screen renders at all`, crashed === 0, crashed ? "CRASHED" : "");
  return crashed === 0;
}

async function walk(key, name, shape, environment) {
  console.log(`\n══ ${key} · ${shape} · ${environment} ═══════════════════════════`);

  // ── 1 · 2 · 3 — the grid, the chip, the card's Connect ───────────────────
  await p.goto(`${BASE}/${T}/settings/integrations`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  await alive("the grid");
  const card = p.locator(`[data-provider-key="${key}"], [data-card="${key}"]`).first();
  const connect = p.locator(`a[data-card-action="connect"][href*="${key}"]`).first();
  const door = (await connect.count()) > 0 ? await connect.getAttribute("href") : null;
  // ⚠ **THIS CHECK IS STATE-AWARE ON PURPOSE, AND THE REASON IS A FINDING.**
  // Once ANY connection row exists the card draws *Manage* and the Connect
  // link is gone — so on a re-run, and on the second environment, there is no
  // door on the grid to the set-up form at all and the address has to be
  // typed. That is `DEF-INT-5548`, filed. A check that scored it as a plain
  // failure would make this script red for ever on a tenant it had already
  // walked, which is how a true red acquires the colouring of a known one.
  if (door === null) {
    console.log(
      "  ·· step 3 · no Connect link: this connector already has a row, so the " +
        "card draws Manage and the second environment has NO DOOR (DEF-INT-5548)",
    );
  } else {
    say(
      "step 3 · Connect on the card is a LINK to its own set-up page",
      door.includes(`/settings/connectors/${key}/configure`),
      door,
    );
  }
  void card;

  // ── 4 · 5 · 6 — the environment, the addresses, the API switches ─────────
  await p.goto(`${BASE}/${T}/settings/connectors/${key}/configure`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1400);
  if (!(await alive("the set-up page"))) return;

  const body = await p.locator("body").innerText();
  say("step 4 · both environments are offered", body.includes("Production") && body.includes("Sandbox"));
  say("the vestigial client id is GONE", !body.includes("Their client id"));
  say("the single-value scope picker is GONE", !body.includes("What they may read"));

  await p.locator(`button:has-text("${environment === "sandbox" ? "Sandbox" : "Production"}")`).first().click();
  await p.waitForTimeout(300);

  const addresses = p.locator('input[id^="field-allowed_addresses"], #field-allowed_addresses').first();
  if ((await addresses.count()) > 0) {
    await addresses.fill("198.51.100.0/24");
    say("step 5 · the allowed addresses take a value", true, "198.51.100.0/24");
  } else {
    say("step 5 · the allowed addresses field is on the screen", false, "not found");
  }

  const switches = p.locator('[role="switch"][data-switch-key]');
  const count = await switches.count();
  say("step 6 · every API row carries its own switch", count > 0, `${count} switches`);
  // Switch the LAST one off, so the key that follows is demonstrably narrower
  // than "everything" — an assertion that all of them are on proves nothing
  // about whether the switch is wired.
  let expected = [];
  for (let i = 0; i < count; i += 1) {
    expected.push(await switches.nth(i).getAttribute("data-switch-key"));
  }
  if (count > 1) {
    // ⚠ **THE ASSERTION IS THAT IT FLIPS, NOT THAT IT ENDS UP OFF.** The
    // switches are seeded from the LIVE KEY's own scope — so re-issuing
    // without touching one cannot silently widen or narrow it — which means
    // on a second walk the last row may start OFF and clicking it turns it ON.
    // A check that demanded "off" would be reading the seed rather than the
    // control, and would fail on exactly the run that proves the seeding works.
    const before = await switches.nth(count - 1).getAttribute("data-switch-state");
    await switches.nth(count - 1).click();
    await p.waitForTimeout(200);
    const after = await switches.nth(count - 1).getAttribute("data-switch-state");
    say("a switch actually flips", before !== after, `${before} → ${after}`);
    if (after === "off") expected = expected.slice(0, count - 1);
  }

  // ── the direction and WHEN words, in this quadrant ───────────────────────
  const rows = await p.locator("[data-operation]").allInnerTexts();
  const directionRight =
    shape === "out · them"
      ? rows.every((one) => one.includes("They read")) && !rows.some((one) => one.includes("They send"))
      : rows.every((one) => one.includes("They send")) && !rows.some((one) => one.includes("They read"));
  say(
    `the DIRECTION word is right for ${shape}`,
    directionRight,
    shape === "out · them" ? "They read" : "They send",
  );
  say("the WHEN column says They call us", rows.every((one) => one.includes("They call us")));
  say("no third vocabulary", !rows.some((one) => /When they (ask|send)/.test(one)));
  const limits = await p.locator("[data-rate-limit]").first().getAttribute("data-rate-limit");
  say("the ceiling column shows a number, not a dash", limits !== null && limits !== "unset", `${limits}/min`);
  say(
    "the limits footnote points the right way: WE allow THEM",
    (await p.locator("[data-limit-note]").innerText()).includes("we allow them"),
  );

  await p.screenshot({ path: `${OUT}/fixed-cfg-${key}-${environment}.png`, fullPage: true });

  // ── 7 vs 9 — WHICH ORDER DOES THE PRODUCT SUPPORT? ──────────────────────
  const generate = p.locator("[data-generate-key]").first();
  const disabledBeforeSave = await generate.isDisabled();
  const noteBeforeSave = (await p.locator("body").innerText()).includes("Save this connector, then generate one.");
  console.log(
    `  ·· STEP ORDER: Generate a key BEFORE Save is ${disabledBeforeSave ? "NOT AVAILABLE" : "available"}` +
      `${noteBeforeSave ? ' — the screen says "Save this connector, then generate one."' : ""}`,
  );

  // ── 9 — Save and test ───────────────────────────────────────────────────
  await p.locator('button:has-text("Save and test")').first().click();
  await p.waitForTimeout(2500);
  const afterSave = await p.locator("body").innerText();
  // ⚠ **THE REFUSAL THIS SCRIPT MISSED FOR TWO RUNS, AND IT IS THE EXACT
  // SHAPE LAW 7 WARNS ABOUT.** The first matcher looked for *"could not"* and
  // *"Check the"*, and the refusal a connected connector actually gives is
  // **"Already connected — open Manage."** — so the walk reported *accepted*
  // over a `409` that the network log had recorded all along. A check whose
  // output cannot tell pass from fail is worse than no check, because it is
  // trusted. The strip is read by its own mark now, not by guessing at words.
  const strips = (await p.locator("[data-refusal], [role=alert]").allInnerTexts()).filter(
    (one) => !one.includes("Set when we configure"),
  );
  const already = strips.some((one) => one.includes("Already connected"));
  if (already) {
    console.log(
      "  ·· step 9 · REFUSED: \"Already connected — open Manage.\" — the set-up " +
        "form is create-only, so the API switches it draws cannot be re-saved " +
        "on a live connector (DEF-INT-5554). Generating a key still takes them.",
    );
  } else {
    say("step 9 · Save and test is accepted", strips.length === 0, strips.join(" | "));
  }

  // ── 7 · 8 — the key, and it is shown once ───────────────────────────────
  await p.goto(`${BASE}/${T}/settings/connectors/${key}/configure`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1400);
  // re-apply the switches: the form is a fresh one after the round trip
  const again = p.locator('[role="switch"][data-switch-key]');
  const n = await again.count();
  if (n > 1) {
    await again.nth(n - 1).click();
    await p.waitForTimeout(200);
  }
  const gen = p.locator("[data-generate-key]").first();
  const pressable = !(await gen.isDisabled());
  say("step 7 · Generate a key can be pressed once the connector is saved", pressable);
  // ⚠ A DISABLED BUTTON IS A FINDING, NOT A CRASH. Clicking one throws after
  // thirty seconds and takes the rest of the walk with it, so the remaining
  // eight checks would report nothing at all rather than reporting a failure —
  // law 7's *a check whose output cannot distinguish pass from fail*.
  if (pressable) {
    await gen.click();
    await p.waitForTimeout(2500);
  }
  const issuedText = await p.locator("[data-issued-key]").count();
  say(
    "step 8 · a key comes back and is shown once",
    issuedText > 0,
    issuedText > 0 ? (await p.locator("[data-issued-key]").innerText()).slice(0, 14) + "…" : "REFUSED",
  );
  await p.screenshot({ path: `${OUT}/fixed-key-${key}-${environment}.png`, fullPage: true });

  // ── 11 — the connection screen ──────────────────────────────────────────
  await p.goto(`${BASE}/${T}/settings/integrations/${key}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1600);
  if (!(await alive("the connection view"))) return;
  const view = await p.locator("body").innerText();
  say("the kicker reads Connector", view.includes("CONNECTOR") || view.includes("Connector"));
  say("no PASSWORDS panel on a connector whose key WE issue", !view.includes("PASSWORDS ON THIS CONNECTION"));
  say("no Replace password", !view.includes("Replace password"));
  const keysTable = await p.locator("[data-keys-table]").count();
  say("the drawn Keys we issue panel is on the screen", keysTable > 0);
  const mayCall = await p.locator("[data-may-call]").allInnerTexts();
  say(
    "MAY CALL names what the key may call, in the clerk's words",
    mayCall.length > 0 && !mayCall.join(" ").includes("serve_"),
    mayCall[0] ?? "no row",
  );
  const describe = await p.locator("[data-describe]").innerText();
  say("the summary line carries the key, not the heading again", describe !== name, describe);
  const when = await p.locator("[data-when]").allInnerTexts();
  say("the WHEN column says They call us here too", when.every((one) => one === "They call us"), when.join(" · "));
  await p.screenshot({ path: `${OUT}/fixed-view-${key}-${environment}.png`, fullPage: true });
  void expected;
}

await walk("erp_workday", "Workday", "out · them", "production");
await walk("payments_kiosk", "Payment kiosk network", "in · them", "production");
// ⚠ THE SAME CONNECTOR, THE OTHER ENVIRONMENT. PO 2026-09-16: *"user can enable
// both"*. Walking 4→9 twice on one connector is the only thing that tests that
// the switches, the key and the activation belong to the ENVIRONMENT rather
// than to the connector.
await walk("erp_workday", "Workday", "out · them", "sandbox");

console.log(`\nERRORS: ${errs.length ? errs.join(" | ") : "none"}`);
console.log(`\n${fails === 0 ? "ALL CHECKS PASSED" : fails + " CHECK(S) FAILED"}`);
await b.close();
process.exit(fails === 0 ? 0 : 1);
