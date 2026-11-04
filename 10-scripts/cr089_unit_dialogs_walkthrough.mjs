// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 · the `U10`, `U11` and `U12` conformance pass.
// Defects: DEF-MET-4761 (two doors out of service, one recording nothing) ·
//          DEF-MET-4731 (two edit forms for one unit) ·
//          DEF-MET-4762 (a retired rule still on screen) ·
//          DEF-MET-4763 (three frames never diffed).
// Rules:   hard-won law 6 — *"diff the running app against the prototype: nine
//          defects were found this way and by nothing else"*, the one law with
//          no tool behind it · the UI skill's §15 close-out.
// ───────────────────────────────────────────────────────
//
// **WHY A BROWSER AND NOT THE 224 GREEN CASES.** Every failure this repo has on
// a screen passes `tsc`, eslint and every test, because no gate here reads
// rendered output. The suites can say a prop is passed and a string exists;
// only this can say the pencil and the ✎ open the SAME form, that the row
// action opens the dialog rather than a confirm, and that the drawn table is on
// screen with its labels in the drawn order.
//
// ⚠ **IT ASSERTS, IT DOES NOT NARRATE.** A walkthrough that prints what it saw
// and exits 0 is a check that cannot fail (hard-won law 7's second shape), so
// every observation below is compared and the run exits non-zero on the first
// mismatch.
//
// ⚠ **AND IT PICKS ITS UNITS BY ASKING THE SERVER**, never by assuming a seeded
// id: one unit with an open account (the refusal is written for that case) and
// one without (the commit can only be watched on that one).
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089-unit-dialogs";
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

let failures = 0;
const say = (...parts) => console.log(...parts);
function check(label, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (!ok) failures += 1;
  say(`${ok ? "  ok  " : "  FAIL"} ${label}`);
  if (!ok) say("        expected", JSON.stringify(expected), "\n        actual  ", JSON.stringify(actual));
}
function present(label, actual) {
  const ok = Boolean(actual);
  if (!ok) failures += 1;
  say(`${ok ? "  ok  " : "  FAIL"} ${label}`);
}

/**
 * Press a row action, wherever the list has put it.
 *
 * ⚠ **THE UNITS LIST GREW A `…` OVERFLOW MENU UNDER THIS WALK (`RowActionsMore`,
 * `CR-089` U1), AND A SELECTOR THAT ONLY KNEW ABOUT ROW BUTTONS RESOLVED TO TWO
 * INVISIBLE ELEMENTS AND TIMED OUT.** The product was correct; the walk was
 * looking in the wrong place — hard-won law 7's fourth shape, for the fourth
 * time in this one file. So it opens the menu when the action is behind it,
 * which is also what a person does.
 */
async function pressRowAction(row, label) {
  const direct = await row.$(`button[aria-label="${label}"], button[title="${label}"]`);
  if (direct !== null && (await direct.isVisible())) {
    await direct.click();
    return;
  }
  const more = await row.$("[data-row-more] summary");
  if (more === null) throw new Error(`no "${label}" on the row and no ... menu to look in`);
  await more.click();
  await row.waitForSelector(`button[title="${label}"], button[aria-label="${label}"]`,
    { state: "visible", timeout: 5000 });
  await (await row.$(`button[title="${label}"], button[aria-label="${label}"]`)).click();
}

/** The <tr> holding a link to `unitId`. */
async function rowFor(unitId) {
  for (const r of await page.$$("tbody tr")) {
    if ((await r.$(`a[href*="${unitId}"]`)) !== null) return r;
  }
  throw new Error(`no row on this list for ${unitId}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const api = (path) =>
  page.evaluate(
    async (p) => {
      const res = await fetch(p, { credentials: "include" });
      return { status: res.status, body: await res.text() };
    },
    path,
  );

const units = JSON.parse((await api(`/api/${TENANT}/units?per=200`)).body).results ?? [];
let held = null;
let free = null;
for (const row of units) {
  if (held !== null && free !== null) break;
  if (row.active === false) continue;
  const view = JSON.parse((await api(`/api/${TENANT}/units/${row.id}/status-change`)).body);
  if (held === null && view.blocked) held = { row, view };
  if (free === null && !view.blocked) free = { row, view };
}
say("units chosen — held:", held?.row?.unit_no ?? "(none)", "· free:", free?.row?.unit_no ?? "(none)");

// ══════════════════════════════════════════════════════════════════════════
// U12 · the row action that used to post the door recording nothing
// ══════════════════════════════════════════════════════════════════════════
say("\nU12 — take a unit out of service, from the UNITS LIST row");
const posts = [];
page.on("request", (r) => {
  if (r.method() === "POST") posts.push(new URL(r.url()).pathname);
});
await page.goto(`${BASE}/${TENANT}/premises/units?f.premises_id=${held.row.premises_id}`, {
  waitUntil: "networkidle",
});
await pressRowAction(await rowFor(held.row.id), "Deactivate");
// ⚠ WAIT FOR THE PANEL, NOT FOR THE DIALOG. The counts arrive from a second
// request, so a screenshot taken on `[data-status-dialog]` is a picture of the
// loading skeleton — an image that cannot show what it was taken to show.
await page.waitForSelector("[data-status-refusal-panel]", { timeout: 15000 });
await page.screenshot({ path: join(OUT, "u12-blocked.png"), fullPage: true });

check(
  "the three drawn inputs are present, in the drawn order",
  await page.$$eval("[data-status-dialog] select, [data-status-dialog] input, [data-status-dialog] textarea",
    (ns) => ns.map((n) => n.id).filter(Boolean)),
  ["status-new", "status-effective-date", "status-reason"],
);
check(
  "New status says in words what the record becomes",
  await page.$eval("#status-new", (n) => n.options[n.selectedIndex].textContent.trim()),
  "Inactive — no longer takes service",
);
present("the refusal panel is drawn", await page.$("[data-status-refusal-panel]"));
check(
  "the refusal panel is a PlainTable",
  await page.$$eval("[data-status-refusal-panel] [data-plaintable]", (ns) => ns.length),
  1,
);
present("no consequence box beside the refusal", (await page.$('[data-consequence="status-change"]')) === null);
check(
  "the account row NAMES the account rather than counting it",
  await page.$eval('[data-dependency="open_accounts"] td', (n) => /^Account \S+ is still open$/.test(n.textContent.trim())),
  true,
);
// ⚠ **THE ORDER IS DRAWN AND IT IS THE ACCOUNT FIRST.** The `U12` frame puts
// `Account … is still open` on row 1 and the meters on row 2; a first run of
// this walk found them the other way round, because the order came from the
// PROPERTY's list. One destination is a single record and the other is a list,
// so the two links are not the same word either.
check(
  "the blocked rows are in the DRAWN order, each with its own link word",
  await page.$$eval("[data-status-refusal-panel] tbody tr", (rows) =>
    rows.map((r) => [
      r.getAttribute("data-dependency"),
      (r.querySelector("td:last-child a")?.textContent ?? "").trim(),
    ])),
  [["open_accounts", "Open it →"], ["attached_assets", "Show them →"]],
);
check("the dialog names the unit by its LABEL, like the other two",
  (await page.$eval(".modal-title", (n) => n.textContent.trim())).includes(held.row.unit_no ?? "\u0000"),
  false);
const commit = (await page.$$(".modal-foot button[data-variant]")).at(-1);
check("the commit wears the drawn label", (await commit.textContent()).trim(), "Deactivate unit");
check("…in the danger tier", await commit.getAttribute("data-variant"), "danger");
check("…and is HELD", await commit.isDisabled(), true);
// ⚠ `force: true` BECAUSE THE BUTTON IS DISABLED, WHICH IS THE POINT. An
// ordinary click waits for it to become enabled and times out — a walkthrough
// failing on the product behaving correctly. Forcing the event through asks the
// real question: can a press get past the hold?
await commit.click({ force: true });
await page.waitForTimeout(800);
check("forcing a press past the hold posts NOTHING", posts.filter((p) => /\/units\//.test(p)), []);
await page.click(".modal-close");

say("\nU12 — the CLEAR state replaces the refusal with the consequence");
await page.goto(`${BASE}/${TENANT}/premises/units?f.premises_id=${free.row.premises_id}`, {
  waitUntil: "networkidle",
});
await pressRowAction(await rowFor(free.row.id), "Deactivate");
await page.waitForSelector('[data-consequence="status-change"]', { timeout: 15000 });
await page.screenshot({ path: join(OUT, "u12-clear.png"), fullPage: true });
present("the consequence is drawn", await page.$('[data-consequence="status-change"]'));
present("…and the refusal panel is NOT", (await page.$("[data-status-refusal-panel]")) === null);
check("the commit is available", await (await page.$$(".modal-foot button[data-variant]")).at(-1).isDisabled(), false);
await page.click(".modal-close");

// ══════════════════════════════════════════════════════════════════════════
// U10 · one edit form, reached from BOTH doors
// ══════════════════════════════════════════════════════════════════════════
say("\nU10 — edit a unit, from the units-list PENCIL");
async function readEditForm() {
  await page.waitForSelector(".modal-card", { timeout: 15000 });
  return {
    title: (await page.$eval(".modal-title", (n) => n.textContent.trim())),
    groups: await page.$$eval("[data-unit-section] h4", (ns) => ns.map((n) => n.textContent.trim())),
    fields: await page.$$eval(".modal-body select, .modal-body input, .modal-body textarea",
      (ns) => ns.map((n) => n.id).filter(Boolean)),
    body: await page.$eval(".modal-card", (n) => n.textContent),
  };
}
// ⚠ **THE SAME UNIT THROUGH BOTH DOORS, OR THE COMPARISON MEANS NOTHING.** A
// first run opened the list's FIRST pencil and the page's ✎ for a different
// unit, then reported the two titles as a mismatch — a check comparing two
// correct answers to two different questions (hard-won law 7's fourth shape).
await page.goto(`${BASE}/${TENANT}/premises/units?f.premises_id=${free.row.premises_id}`, {
  waitUntil: "networkidle",
});
await pressRowAction(await rowFor(free.row.id), "Edit");
const fromList = await readEditForm();
await page.screenshot({ path: join(OUT, "u10-from-list.png"), fullPage: true });
check("the four drawn group headings, in the drawn order",
  fromList.groups.map((g) => g.replace(/\s*optional\s*$/, "").trim()),
  ["What this unit is called", "Where it is", "What it can take", "What it is charged on"]);
present("the retired 'a unit never moves' sentence is gone",
  !fromList.body.includes("never moves between premises"));
present("no undrawn Premise field", !fromList.fields.includes("premise"));
present("the common-area question is on the form", fromList.fields.includes("is_common_area"));
present("the services sentence names the building", fromList.body.includes("These come from the building"));
present("the point OFFER is drawn, not two empty boxes",
  !fromList.fields.includes("lat") && fromList.body.includes("point"));
await page.click(".modal-close");

say("\nU10 — and from the unit's OWN page ✎ Edit");
await page.goto(`${BASE}/${TENANT}/premises/units/${free.row.id}`, { waitUntil: "networkidle" });
await page.click('button:has-text("Edit")');
const fromPage = await readEditForm();
await page.screenshot({ path: join(OUT, "u10-from-page.png"), fullPage: true });
check("DEF-MET-4731 — the two doors open the SAME form", fromPage.groups, fromList.groups);
check("…with the same fields, in the same order", fromPage.fields, fromList.fields);
check("…and the same title", fromPage.title, fromList.title);
present("B14 rule 31 — the title is the LABEL, not the series number",
  free.row.unit_no === null || !fromPage.title.includes(free.row.unit_no));
await page.click(".modal-close");

// ══════════════════════════════════════════════════════════════════════════
// U11 · move a unit
// ══════════════════════════════════════════════════════════════════════════
say("\nU11 — move a unit to another property");
await page.click('button:has-text("Move")');
await page.waitForSelector("#premises_id", { timeout: 15000 });
check("Currently on reads ADDRESS first",
  (await page.$eval("#move-from", (n) => n.value)).startsWith(free.row.premise_address ?? ""), true);
present("Move to is marked required", await page.$("#premises_id[aria-required='true']"));
// ⚠ `SearchSelectField` IS IS-3's TYPE-AHEAD: it opens on a QUERY, not on a
// click, with a 300 ms debounce and a two-character minimum. Clicking it and
// reading zero options would be a walkthrough reporting the control as broken
// because it drove it wrongly.
await page.click("#premises_id");
await page.fill("#premises_id", "0");
await page.waitForTimeout(900);
const option = await page.$("[role='option']");
if (option !== null) {
  await option.click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(OUT, "u11-consequence.png"), fullPage: true });
  check("WHAT THIS WILL DO is a labelled TABLE with the seven drawn rows",
    await page.$$eval("[data-move-consequence] tbody tr [data-effect], [data-move-consequence] tbody tr",
      (ns) => ns.map((n) => n.getAttribute("data-effect")).filter(Boolean)),
    ["issuedBills", "nextBill", "accounts", "bills", "route", "assets", "recorded"]);
  check("…and the drawn labels are the left column",
    await page.$$eval("[data-move-consequence] tbody tr td:first-child", (ns) => ns.map((n) => n.textContent.trim())),
    ["Bills already issued", "The next bill", "Accounts this unit has carried",
     "Bills it has produced", "Route and cycle", "Meters and assets", "Recorded"]);
} else {
  say("  note  no other property to move to on this tenant — the table could not be opened");
}
check("the commit wears the drawn label and the danger tier",
  await page.$$eval(".modal-foot button[data-variant]",
    (ns) => [ns.at(-1).textContent.trim(), ns.at(-1).getAttribute("data-variant")]),
  ["Move unit ✓", "danger"]);

await browser.close();
say(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`} — screenshots in ${OUT}`);
process.exit(failures === 0 ? 0 : 1);
