// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 … US-CWP-066 — every screen CR-068 ships, opened in a
//           real browser. Screens: all 50 in `src/portal/routing/screenIds.ts`
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · CR-068 R3 (a control is held UNTIL its screen lands)
//           · B14 rule 31 (no database id is ever the visible value of a field)
// Defects:  DEF-CWP-3925 (six doors shut over live screens) · DEF-CWP-3926
//           (the engine's diagnostics printed on the customer's home page) —
//           both found HERE and by nothing else, with 42 test files green
// ───────────────────────────────────────────────────────
/**
 * cwp_portal_walkthrough — open all 50 portal screens and say what is wrong.
 *
 *     # one terminal: a real PostgreSQL with the portal fixture in it
 *     DATABASE_URL=… python manage.py seed_portal_demo
 *     DATABASE_URL=… ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8099
 *     # another: the built bundle, proxying /api at it
 *     cd 07-frontend && npx vite build
 *     PORT=4299 API_PROXY_TARGET=http://127.0.0.1:8099 node server.mjs
 *     SHOTS=07-frontend/shots node 10-scripts/cwp_portal_walkthrough.mjs
 *
 * ⚠ **REBUILD THE BUNDLE BEFORE YOU WALK — A RUNNING `node server.mjs` SERVES
 * WHATEVER WAS IN `dist/` WHEN IT STARTED, FOREVER.** `server.mjs` reads files
 * off disk per request, so it never restarts itself and never notices that
 * `dist/` is hours old; it prints the directory it serves at boot and nothing
 * afterwards. On 2026-09-05 a server started at 03:16 was still serving a
 * bundle built before the six payment screens existed, and every one of them
 * answered with the PREVIOUS wave's holding page — which is indistinguishable,
 * in a screenshot, from six screens that were never built. `cd 07-frontend &&
 * npx vite build` FIRST, then confirm the hash the page actually loaded is the
 * hash you just built:
 *
 *     curl -s $BASE/index.html | grep -o 'index-[A-Za-z0-9_-]*\.js'
 *
 * ⚠ **AND `dist/` IS RESOLVED FROM `server.mjs`'s OWN DIRECTORY, NOT FROM
 * `cwd`.** A lane working in a `git worktree` that runs the shared checkout's
 * `node /home/user/SMARTBillHub/07-frontend/server.mjs` serves the SHARED
 * checkout's `dist/` however carefully it just built its own — the same trap
 * one level up, and the boot line is the only place it shows. Pass
 * `STATIC_DIR` explicitly and read that line back.
 *
 * ⚠ **`playwright` IS RESOLVED FROM `07-frontend`, EXPLICITLY, AND THAT IS NOT
 * FUSSINESS.** Node resolves a bare import from the SCRIPT's own directory
 * upward — never from the working directory — so `import { chromium } from
 * "playwright"` in a file under `10-scripts/` fails with `ERR_MODULE_NOT_FOUND`
 * however you invoke it, and the repo root has no `node_modules`. The first
 * version of this file carried a comment telling the reader to run it from
 * `07-frontend`, which is hard-won law 1 exactly: a comment claiming a
 * guarantee is not the guarantee, and this one was simply wrong about how the
 * runtime works. `createRequire` against the frontend's own `package.json` is
 * the guarantee.
 *
 * It prints one line per screen — the `data-screen` id it found, a word count,
 * the address — then the doors on the front page, then every JS error and every
 * API call that answered 400 or worse. A screen with no id, or under 25 words,
 * is the line to go and look at.
 *
 * ⚠ **THE ROUTE LIST IS PARSED OUT OF `screenIds.ts`, NOT TYPED HERE.** A
 * hand-kept second list is hard-won law 12's shape for pointers: a wave adds a
 * screen, the register grows, and the walkthrough goes on reporting a clean run
 * over a screen it never opened. Parsing the register means a new row is walked
 * the day it lands, and it also lets this script say which `CWP` ids it did NOT
 * reach — the sentence that would have named the six payment screens hours
 * before anyone looked.
 *
 * ⚠ **RESTART THE API SERVER BEFORE YOU BELIEVE A BLANK SCREEN.** `runserver
 * --noreload` serves the code it started with, and on 2026-09-05 five screens
 * came back empty against a server six hours old whose routes predated them.
 * Every endpoint answered 200 the moment it was restarted. A stale server looks
 * exactly like a broken product and is the first thing to rule out.
 *
 * ⚠ **AND CHECK WHICH DATABASE IT IS POINTED AT BEFORE YOU BELIEVE A `401`.**
 * On 2026-09-05 a walkthrough was handed the name of a demo database that held
 * 200 invoices and NOT ONE `portal_credential` row, so sign-in answered
 * `{"ok":false,"reason":"wrong"}` — which reads exactly like a broken login and
 * is a fixture that was never enrolled. `select count(*) from portal_credential`
 * costs one command and rules it out.
 *
 * ⚠ **NEVER `waitUntil: "networkidle"` HERE.** The portal shell holds a
 * connection open, so it never settles: each `goto` silently burns its full
 * 30-second timeout inside a `.catch(() => {})` and a 35-page run takes hours.
 * Three runs were lost to that before anyone measured it — `domcontentloaded`
 * plus a wait for `[data-screen], main` does the same job in seconds.
 *
 * ⚠ **A `429` IN THE PROBLEM LIST IS USUALLY THIS SCRIPT, NOT THE PRODUCT.**
 * The guest edge throttles per address AND per tenant (`NFR-38`-`NFR-41`), and
 * a walkthrough opening forty pages from one address in ten minutes is exactly
 * the shape it exists to refuse. Two guest reads were refused this way on
 * 2026-09-05 and both are correct behaviour. Read a `429` as *slow down and
 * run the guest half again*, and only chase it if it names a SIGNED-IN route,
 * where the throttle does not apply.
 *
 * ⚠ **AND THE SCRIPT ITSELF USED TO REPORT ONE AS AN ABSENCE** — `firstOf`
 * returned `null` for any non-OK answer, so a throttled read of the service
 * centres printed *"no service centre — CWP-014 NOT WALKED"*, which is a claim
 * about the FIXTURE and was simply false. It now returns a tagged answer and
 * the caller says *refused — rerun the guest half*. See the block above
 * `firstOf` for why that distinction is the whole point of the check.
 *
 * ⚠ **THE 4xx CAPTURE MATTERS AS MUCH AS THE 5xx ONE.** Every portal screen
 * catches its own read failure and draws a sentence, so a 404 from the API
 * reaches the page as a tidy *"we could not read this"* and reaches this script
 * as a healthy-looking screenshot. Only the response listener sees it.
 *
 * ⚠ **THE LOGIN DECIDES WHAT THIS PROVES.** A customer holding an account with
 * no bills exercises every signed-in screen in its EMPTY state and none of them
 * populated — which is half a walkthrough, and reads as a clean run.
 *
 * WHAT IT ASSERTS BEYOND A WORD COUNT, and why each one is here:
 *
 *   HOLDING   `[data-holding-screen]` anywhere. Six screens were holding pages
 *             hours before this was written; failing on a survivor is the guard
 *             that says a lane did not finish.
 *   KEY       a raw i18n key rendered as visible text. The key set is loaded
 *             from `en.json`, so a key RENAMED after a merge — which renders as
 *             its own dotted path — is caught by the SHAPE even when the set no
 *             longer holds it.
 *   ID        `apps.…` module paths, `BR-`/`OQ-`/`DEF-`/`US-` ids and bare
 *             uuids. B14 rule 31 and BR-CWP-021: none of these is ever a thing
 *             a customer sees. One screen printed module paths under a balance.
 *   HELD      every `[data-held]` control and every disabled button, with the
 *             reason it carries — because a reason stops being true on the day
 *             the screen it names lands, and nothing else in this repo asks
 *             (DEF-CWP-3925).
 *   LINK      every `href` the page emits, checked for the `//portal/…`
 *             protocol-relative shape a missing `:tenant` produces. That string
 *             passes `toContain` in a unit test and points at another host in a
 *             browser.
 *   NO LINK   the crawl at the end. Every check above TYPES AN ADDRESS IN, so
 *             none of them can tell a live screen from a live screen nobody
 *             can reach — which is `DEF-CWP-3925` from the other side. The
 *             crawl follows ANCHORS only, from the front page and from home,
 *             resolving each `href` against the page's own URL because a
 *             relative one is a real door. **It cannot see a `<button>` that
 *             calls `navigate()`** — `CWP-002`'s Pay control is one — so read a
 *             NO LINK line as *no anchor points here* and confirm by hand
 *             before calling a screen unreachable.
 */
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
const BASE = process.env.BASE ?? "http://127.0.0.1:4299";
const OUT = process.env.SHOTS;
const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = join(HERE, "..", "07-frontend");
const TENANT = process.env.PORTAL_TENANT ?? "pine-hill";

// ── the register, parsed rather than retyped ─────────────────────────────
// One row per CWP screen: `{ path, id, blueprint, title }`. Parsing it means a
// wave that adds a screen gets it walked without touching this file, and lets
// the run end by NAMING the ids it never reached.
const REGISTER = [
  ...readFileSync(join(FRONTEND, "src/portal/routing/screenIds.ts"), "utf8").matchAll(
    /\{\s*path:\s*"([^"]*)",\s*id:\s*"(CWP-\d+)",\s*blueprint:\s*"([^"]*)",\s*title:\s*"([^"]*)"/g,
  ),
].map(([, path, id, blueprint, title]) => ({ path, id, blueprint, title }));
if (REGISTER.length === 0) throw new Error("parsed no rows out of screenIds.ts — the shape moved");

// Every locale key, flattened, so a rendered key can be recognised by NAME as
// well as by shape.
const KEYS = new Set();
(function flatten(node, prefix) {
  if (node && typeof node === "object" && !Array.isArray(node)) {
    for (const [k, v] of Object.entries(node)) flatten(v, prefix ? `${prefix}.${k}` : k);
  } else if (prefix) KEYS.add(prefix);
})(JSON.parse(readFileSync(join(FRONTEND, "src/i18n/locales/en.json"), "utf8")), "");

const KEY_SHAPE = /\b(?:portal|integrations)\.[a-z][A-Za-z0-9]*(?:\.[A-Za-z0-9_]+)+\b/g;
const MODULE_PATH = /\bapps\.[a-z_]+(?:\.[a-z_]+)+\b/g;
const REPO_ID = /\b(?:BR|OQ|DEF|US|EP|GT|ADR|IS)-(?:[A-Z]{2,4}-)?\d{1,5}\b/g;
const UUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;

//: ⚠ An explicit path, because the pinned @playwright/test wants a build this
//: image does not carry. `PW_CHROME` overrides it; without either, Playwright's
//: own lookup runs and says which build it wanted.
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const browser = await chromium.launch(
  existsSync(CHROME) ? { executablePath: CHROME } : {},
);
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const problems = [];
const findings = [];
page.on("pageerror", (e) => problems.push(`  JS ERROR ${page.url()}: ${e.message.slice(0, 140)}`));
page.on("response", (r) => {
  if (r.status() >= 400 && r.url().includes("/api/")) problems.push(`  ${r.status()} ${r.url().replace(BASE, "")}`);
});

const seen = new Set();

/** Everything a customer can actually read on the page, with the chrome kept. */
async function visibleText() {
  return (await page.locator("body").innerText().catch(() => "")).trim();
}

async function look(path, name, tag, expectId) {
  // ⚠ NOT `networkidle` — the portal shell keeps a connection open, so it
  // never settles and every goto burns its full 30s timeout in silence. Three
  // walkthrough runs were lost to that before it was measured.
  await page.goto(BASE + path, { waitUntil: "domcontentloaded", timeout: 15000 }).catch(() => {});
  await page.waitForSelector("[data-screen], main", { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(700);
  const text = await visibleText();
  const screen = await page.getAttribute("[data-screen]", "data-screen").catch(() => null);
  // Every `data-screen` on the page, not only the first: `/enrol` draws three
  // and `/start-service/:draft` two, and the register names only the landing one.
  const allScreens = await page
    .$$eval("[data-screen]", (n) => n.map((e) => e.getAttribute("data-screen")))
    .catch(() => []);
  for (const s of allScreens) seen.add(s);
  const words = text.split(/\s+/).filter(Boolean).length;
  if (OUT) await page.screenshot({ path: `${OUT}/${tag}-${name}.png`, fullPage: true }).catch(() => {});

  const flags = [];
  // ── HOLDING ── a lane's placeholder that outlived its wave.
  const holding = await page
    .$$eval("[data-holding-screen]", (n) => n.map((e) => e.getAttribute("data-holding-screen")))
    .catch(() => []);
  if (holding.length) flags.push(`HOLDING(${holding.join(",")})`);

  // ── KEY ── a raw translation key rendered as text.
  const byShape = [...new Set(text.match(KEY_SHAPE) ?? [])];
  const byName = [...new Set(text.split(/\s+/).filter((w) => KEYS.has(w.replace(/[.,;:]$/, ""))))];
  const leakedKeys = [...new Set([...byShape, ...byName])];
  if (leakedKeys.length) flags.push(`KEY(${leakedKeys.slice(0, 4).join(" ")})`);

  // ── ID ── module paths, repo ids, uuids: none is a customer's business.
  const ids = [
    ...new Set([
      ...(text.match(MODULE_PATH) ?? []),
      ...(text.match(REPO_ID) ?? []),
      ...(text.match(UUID) ?? []),
    ]),
  ];
  if (ids.length) flags.push(`ID(${ids.slice(0, 4).join(" ")})`);

  // ── HELD ── every refusal on the page, with the reason it gives.
  //: `:not(:has([data-held]))` so a `HeldButton` — a `[data-held]` wrapper
  //: around a `button[disabled]` — is counted ONCE. Without it the front page
  //: reports two holds over one control, which reads as a second defect.
  const heldControls = await page
    .$$eval("[data-held]:not(:has([data-held])), button[disabled]:not([data-held] button), a[aria-disabled='true']", (nodes) =>
      nodes.map((n) => ({
        label: (n.querySelector("button")?.textContent ?? n.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 70),
        reason: (n.getAttribute("title") ?? n.querySelector("[title]")?.getAttribute("title") ?? "")
          .replace(/\s+/g, " ")
          .slice(0, 130),
      })),
    )
    .catch(() => []);
  if (heldControls.length) flags.push(`HELD(${heldControls.length})`);

  // ── LINK ── the `//portal/…` shape a missing `:tenant` makes.
  const hrefs = await page.$$eval("a[href]", (n) => n.map((e) => e.getAttribute("href"))).catch(() => []);
  const broken = [...new Set(hrefs.filter((h) => h && (h.startsWith("//") || h.includes("/undefined/"))))];
  if (broken.length) flags.push(`LINK(${broken.slice(0, 3).join(" ")})`);

  const wrong = expectId && screen && screen !== expectId ? ` ✗ expected ${expectId}` : "";
  const empty = words < 25 ? " ⚠ NEARLY EMPTY" : "";
  console.log(
    `${(screen || "—").padEnd(9)} ${String(words).padStart(4)}w  ${path}${empty}${wrong}${flags.length ? "  " + flags.join(" ") : ""}`,
  );
  if (flags.length || wrong || empty)
    findings.push({ path, name, screen, expectId, words, flags, heldControls, leakedKeys, ids, holding, broken });
  return { path, name, words, screen, flags, heldControls };
}

// A register row becomes an address: `/` is the portal root, a `:param` is
// filled from what the API actually holds (see `firstOf` below).
const rel = (p) => `/${TENANT}/portal` + (p === "/" ? "" : p);
const PARAMLESS = REGISTER.filter((r) => !r.path.includes(":"));
const PARAMED = REGISTER.filter((r) => r.path.includes(":"));

// Which of the paramless rows a stranger can open without signing in. Anything
// not named here is walked after the sign-in below.
const GUEST_PATHS = new Set([
  "/",
  "/report",
  "/track",
  "/help",
  "/start-service",
  "/ask",
  "/pay",
  "/pay/check",
  "/pay/done",
  "/visit",
  "/enrol",
  "/forgot-password",
  "/sign-in",
]);

console.log(`── guest (${GUEST_PATHS.size} of ${REGISTER.length} registered screens) ──`);
for (const row of PARAMLESS.filter((r) => GUEST_PATHS.has(r.path))) await look(rel(row.path), row.id, "g", row.id);

// ── DEF-CWP-3925: press the doors, do not merely count the words ──────────
// The defect this run is verifying was three `<span>`s and a disabled button
// that LOOKED like a nav. Word counts and screenshots both showed a healthy
// page. So the check is: collect every href the frame emits, then follow the
// ones that matter and read the id of the screen that answers.
await page.goto(BASE + rel("/"), { waitUntil: "domcontentloaded" });
await page.waitForTimeout(900);
const doors = await page.$$eval("header a, [data-errand] a", (nodes) => nodes.map((n) => n.getAttribute("href")));
console.log("\n── doors on the front page ──");
console.log("  " + (doors.length ? doors.join("\n  ") : "NONE — every door on the front page is dead"));
const frontHeld = await page.$$eval("[data-held]:not(:has([data-held])), button[disabled]:not([data-held] button)", (n) =>
  n.map((e) => (e.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 100)),
);
console.log(`  held controls still on the front page: ${frontHeld.length}`);
for (const h of frontHeld) console.log(`    · ${h}`);
// Every card on the front page, and where its action goes — a card whose action
// is not a link is a door that does not open, which is what DEF-CWP-3925 was.
const cards = await page.$$eval("[data-errand]", (nodes) =>
  nodes.map((n) => ({
    key: n.getAttribute("data-errand"),
    href: n.querySelector("a")?.getAttribute("href") ?? null,
    disabled: !!n.querySelector("button[disabled]"),
    tail: (n.querySelector("[title]")?.getAttribute("title") ?? "").replace(/\s+/g, " ").slice(0, 100),
  })),
);
console.log("\n── the cards on the front page ──");
for (const c of cards)
  console.log(`  ${(c.key ?? "?").padEnd(18)} ${c.href ? "→ " + c.href : c.disabled ? "HELD: " + c.tail : "— no action"}`);

// ⚠ Sign in through the API and hand the cookie to the browser. Driving the
// form is the more faithful test, but a selector that silently misses leaves
// every later screen showing "You're signed out" — which is what happened on
// the first run and cost 20 minutes of screenshots of an error page.
//: `PORTAL_LOGIN` because the login decides what the run proves — a customer
//: holding an account with no bills walks every signed-in screen in its EMPTY
//: state, which reads as a clean run and proves half of one.
const LOGIN = process.env.PORTAL_LOGIN ?? "ana@example.test";
const api = await page.request.post(BASE + `/api/${TENANT}/portal/auth/sign-in`, {
  data: { email: LOGIN, password: process.env.PORTAL_PASSWORD ?? "Pine-Hill-2026!" },
});
if (!api.ok()) {
  console.log("SIGN-IN FAILED", api.status(), (await api.text()).slice(0, 200));
  process.exit(1);
}
await page.goto(BASE + rel("/home"), { waitUntil: "domcontentloaded" });
await page.waitForTimeout(900);
const signedOut = (await visibleText()).includes("signed out");
console.log(signedOut ? "\n⚠ STILL SIGNED OUT — the walk below is meaningless\n" : `\nsigned in as ${LOGIN}\n`);

console.log("── signed in ──");
const rows = [];
for (const row of PARAMLESS.filter((r) => !GUEST_PATHS.has(r.path))) rows.push(await look(rel(row.path), row.id, "s", row.id));
// The guest doors again, this time with a session — a signed-in customer sees a
// different page at several of them and it is a page nobody walks otherwise.
console.log("\n── the guest doors, with a session ──");
for (const row of PARAMLESS.filter((r) => GUEST_PATHS.has(r.path) && r.path !== "/"))
  rows.push(await look(rel(row.path), row.id + "-in", "si", null));

// ── THE SCREENS AN ADDRESS CANNOT REACH WITHOUT A REFERENCE ──────────────
// A bill screen needs a bill NUMBER, an answer needs its slug, a centre needs
// its own. Hardcoding any of them would rot the first time the fixture moved,
// so each is DISCOVERED from the API the screen itself reads — which also means
// a run against an account with nothing on it says so, out loud, instead of
// quietly walking 36 screens and calling it 50.
// ⚠ **AN ABSENCE AND A REFUSAL ARE DIFFERENT ANSWERS AND THIS FUNCTION USED TO
// GIVE THEM THE SAME ONE.** It was `if (!answer.ok()) return null`, so a `429`
// came back as `null` and the caller printed *"no service centre — CWP-014 NOT
// WALKED"* — a sentence that names an absence when the truth is that the read
// was throttled and the centre is right there. A run printed exactly that line
// beside `429 …/public/service-centres` in its own problem list: two lines, one
// cause, and only one of them true.
//
// **It is the hazard `DEF-182` records, inside our own instrument:** a check
// whose output cannot distinguish one outcome from another is worse than no
// check, because it is trusted — and this one silently downgraded a screen from
// walked to not-walked while asserting something false about the fixture.
//
// So it returns a TAGGED answer: `{ value }` when the list held something,
// `{ empty: true }` when the read succeeded and the list was empty, and
// `{ refused: <status> }` when the edge refused. The guest throttle is per
// address AND per tenant and this script is exactly the shape it exists to
// refuse, so a `429` gets ONE retry after `Retry-After` (default a second)
// before that verdict stands.
async function firstOf(path, key, pick, { retry = true } = {}) {
  const answer = await page.request.get(BASE + `/api/${TENANT}/portal` + path);
  if (answer.status() === 429 && retry) {
    const after = Number(answer.headers()["retry-after"] ?? 1);
    await page.waitForTimeout(Math.min(Number.isFinite(after) ? after : 1, 30) * 1000);
    return firstOf(path, key, pick, { retry: false });
  }
  if (!answer.ok()) return { refused: answer.status() };
  const body = await answer.json().catch(() => null);
  const found = body?.[key];
  if (!Array.isArray(found) || found.length === 0) return { empty: true };
  return { value: pick(found[0]) };
}

console.log("\n── screens reached by reference ──");
const billNumber = await firstOf("/bills", "bills", (b) => b.number);
const requestRef = await firstOf("/requests", "requests", (r) => r.reference ?? r.number);
const answerSlug = await firstOf("/public/help", "answers", (a) => a.slug);
const centreSlug = await firstOf("/public/service-centres", "centres", (c) => c.slug);

/** The true reason a reference is missing — never an absence when it was a refusal. */
function why(found, absence) {
  if (found.refused === 429) return "REFUSED by the guest throttle — rerun the guest half";
  if (found.refused !== undefined) return `REFUSED ${found.refused} by the API — chase this`;
  return absence;
}

for (const row of PARAMED) {
  let addr = row.path;
  const need = (found, absence) => {
    if (found.value === undefined) {
      console.log(`  ${row.id} ${row.path} — NOT WALKED: ${why(found, absence)}`);
      return null;
    }
    return found.value;
  };
  if (addr.includes(":number")) {
    const got = need(billNumber, "no bill on this login");
    if (got === null) continue;
    addr = addr.replace(":number", got);
  }
  if (addr.includes(":reference")) {
    const got = need(requestRef, "no request on this login");
    if (got === null) continue;
    addr = addr.replace(":reference", got);
  }
  if (addr.includes(":slug")) {
    const got = need(
      row.path.startsWith("/help") ? answerSlug : centreSlug,
      row.path.startsWith("/help") ? "nothing published" : "no service centre",
    );
    if (got === null) continue;
    addr = addr.replace(":slug", got);
  }
  if (addr.includes(":draft")) {
    console.log(`  ${row.id} ${row.path} — NOT WALKED: a draft link is minted by the form`);
    continue;
  }
  rows.push(await look(rel(addr), row.id, "d", row.id));
}

// ── CAN A CUSTOMER GET THERE? ─────────────────────────────────────────────
// ⚠ **A SCREEN THAT ANSWERS AT ITS ADDRESS IS NOT A SCREEN A CUSTOMER CAN
// REACH, AND EVERY CHECK ABOVE TYPES THE ADDRESS IN.** That is hard-won law 2
// — *built is not wired* — in the shape the portal keeps producing it: a wave
// lands a screen, tests it at its own address, and the door that was supposed
// to start pointing at it belongs to nobody (`DEF-CWP-3925`). The walkthrough
// itself cannot see it, because a walkthrough that navigates by URL proves
// only that the router works.
//
// So: crawl. Follow every `href` from the front page and from home, breadth
// first, staying inside `/{tenant}/portal`, and report which registered
// screens NO link anywhere points at. A screen in that list is either
// deliberately deep (reached from a row, a form, a bill) or it is unreachable
// — and the difference is a judgment a person makes, which is why this prints
// a list rather than failing.
//
// ⚠ **RESOLVE EVERY `href` AGAINST THE PAGE'S OWN URL — A RELATIVE ONE IS A
// REAL DOOR AND THE FIRST VERSION OF THIS CRAWL COULD NOT SEE IT.** `HelpPage`
// writes `href="help/<slug>"`, which a browser resolves to
// `/pine-hill/portal/help/<slug>` and which `startsWith("/pine-hill/portal")`
// rejects out of hand. So the crawl reported *"NO LINK CWP-060"* over six rows
// that are ordinary anchors — the same class of mistake as `firstOf` calling a
// refusal an absence, made by the same author twenty minutes later. **A
// reachability check that under-reports is worse than none, because its output
// is a list of screens somebody will go and "fix".**
//
// ⚠ **AND IT STILL UNDER-REPORTS BY ONE MECHANISM: a `<button>` that calls
// `navigate()`.** `CWP-002`'s *Pay* control is one, and it opens `CWP-003`; no
// anchor anywhere names `/pay/check`. Nothing in the DOM distinguishes such a
// button from an inert one, so the honest posture is to say so — read a NO
// LINK line as *no ANCHOR points here*, and confirm by hand before calling a
// screen unreachable.
console.log("\n── can a customer get there? (anchors followed, not typed) ──");
const linked = new Set();
const crawled = new Set();
const queue = [rel("/"), rel("/home")];
while (queue.length) {
  const here = queue.shift();
  if (crawled.has(here) || crawled.size > 60) continue;
  crawled.add(here);
  await page.goto(BASE + here, { waitUntil: "domcontentloaded", timeout: 15000 }).catch(() => {});
  //: ⚠ **1500ms, AND IT IS NOT PADDING.** Several screens draw their onward
  //: links only after their own read lands — `/usage` renders *Every reading*
  //: and *Meters and equipment* from the data, not from the shell. At 250ms
  //: this crawl reported both as NO LINK, which is a reachability check
  //: inventing an unreachable screen. If this run is ever made faster, make it
  //: wait for a settled DOM rather than shortening the clock.
  await page.waitForTimeout(1500);
  const hrefs = await page
    .$$eval(
      "a[href]",
      (n, base) =>
        n.map((e) => {
          try {
            return new URL(e.getAttribute("href"), base).pathname;
          } catch {
            return null;
          }
        }),
      page.url(),
    )
    .catch(() => []);
  for (const raw of hrefs) {
    if (!raw || !raw.startsWith(`/${TENANT}/portal`)) continue;
    const clean = raw.split("?")[0].split("#")[0].replace(/\/$/, "");
    linked.add(clean);
    if (!crawled.has(clean)) queue.push(clean);
  }
}
// A registered row is "linked" when some href matched its address — for a
// `:param` row, when an href matched the shape with anything in the slot.
const shapeOf = (p) =>
  new RegExp(`^${rel(p).replace(/:[A-Za-z]+/g, "[^/]+").replace(/\//g, "\\/")}$`);
const unlinked = REGISTER.filter((r) => ![...linked].some((h) => shapeOf(r.path).test(h)));
console.log(`  ${crawled.size} pages crawled · ${linked.size} distinct portal addresses linked to`);
console.log(`  ${REGISTER.length - unlinked.length} of ${REGISTER.length} registered screens have a link somewhere`);
for (const u of unlinked) console.log(`  NO LINK      ${u.id}  ${u.path}  (${u.title})`);

// ── did every registered screen actually answer? ──────────────────────────
// The sentence that would have named the six payment screens hours earlier.
console.log("\n── register coverage ──");
const missing = REGISTER.filter((r) => !seen.has(r.id));
console.log(`  ${REGISTER.length} registered · ${seen.size} distinct data-screen ids observed`);
for (const m of missing) console.log(`  NOT OBSERVED  ${m.id}  ${m.path}  (${m.title})`);
const extra = [...seen].filter((s) => !REGISTER.some((r) => r.id === s));
if (extra.length) console.log(`  observed but NOT in the register: ${extra.join(", ")}`);

console.log("\n── problems ──");
console.log(problems.length ? [...new Set(problems)].join("\n") : "  none");

console.log("\n── findings ──");
if (!findings.length) console.log("  none");
for (const f of findings) {
  console.log(`  ${f.path}`);
  if (f.holding?.length) console.log(`    HOLDING SCREEN: ${f.holding.join(", ")}`);
  if (f.leakedKeys?.length) console.log(`    RAW KEYS: ${f.leakedKeys.join(", ")}`);
  if (f.ids?.length) console.log(`    IDS VISIBLE: ${f.ids.join(", ")}`);
  if (f.broken?.length) console.log(`    BROKEN LINKS: ${f.broken.join(", ")}`);
  if (f.expectId && f.screen && f.screen !== f.expectId)
    console.log(`    WRONG SCREEN: got ${f.screen}, register says ${f.expectId}`);
  if (f.words < 25) console.log(`    NEARLY EMPTY: ${f.words} words`);
  for (const h of f.heldControls ?? []) console.log(`    HELD: "${h.label}" — ${h.reason || "(no reason given)"}`);
}
const empty = rows.filter((r) => r.words < 25);
console.log(`\n${rows.length} signed-in screens, ${empty.length} nearly empty: ${empty.map((e) => e.name).join(", ") || "none"}`);
await browser.close();
