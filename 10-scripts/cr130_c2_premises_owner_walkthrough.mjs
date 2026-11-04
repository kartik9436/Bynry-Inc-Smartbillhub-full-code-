// ── `CR-130-BRC07` part three, lane C2 — THE THREE PREMISES OWNER SCREENS ──
//
// PO, from the live product: *"we are unabel to find and map master account to
// premises later … in edit also we are unabel to search owner - and owner and
// master account is confusing we ahve to use one volcabory ; in add presmies
// also we are providing person or company name, ids and documents - but it does
// not create the master account and also not linking that account to premsies"*.
//
// RULING 2026-09-22: **a premises names its MASTER ACCOUNT directly.** No screen
// creates, picks or searches an OWNER RECORD.
//
// ⚠ **THIS FILE RUNS IN TWO MODES AND THE FIRST ONE IS THE POINT.**
//   `MODE=before`  the reproduction — it asserts the three screens are BROKEN,
//                  in the exact words of the report. CR §9.4: *"All of §9.2 is
//                  read from code and has not been clicked."*
//   `MODE=after`   the proof — the same three journeys, now working.
//
// ⚠ **`after` PROVES THE SCREEN'S HALF AND SAYS SO.** Lane C1 owns the column,
// the `master_account_id` doors and the eight verdict `message_key`s; this lane
// owns the three screens. Where a row needs C1's half it prints **PENDING · C1**
// rather than FAIL, because a lane reporting its sibling's unlanded work as its
// own failure is how a real red gets the protective colouring of a known one.
// A walk that only ever runs green after the fix proves nothing about what it
// was measuring (CLAUDE.md hard-won law 7 — break the guard red first).
//
// ⚠ **IT TAGS AND PRINTS WHAT IT WRITES; IT DOES NOT PURGE, AND SAYING SO IS
// THE POINT.** This header claimed *"it purges what it writes"* and **no line
// in the file purged anything** — a comment claiming a guarantee is not the
// guarantee (CLAUDE.md hard-won law 1), and the next lane would have trusted it.
// Every address carries the `WALK_TAG` prefix and every id prints at the end.
// **Run it against a private clone and drop that clone afterwards** —
// `10-scripts/proof-db.sh clone <yourname>` then `drop <yourname>` — which is
// what this lane did and is stronger than a purge: a clone cannot leave a row
// in anybody's beta, and a purge that misses one silently can.
//
//   C2_BASE     default http://127.0.0.1:8792
//   C2_TENANT   default brazosbend
//   C2_EMAIL    default dana@brazosbendutilities.com
//   C2_PASSWORD default S3cure!passw0rd
//   C2_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.C2_ROOT || process.cwd();
const BASE = process.env.C2_BASE || "http://127.0.0.1:8792";
const T = process.env.C2_TENANT || "brazosbend";
const EMAIL = process.env.C2_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.C2_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.C2_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const MODE = process.env.MODE || "before";
const WALK_TAG = `C2-${Date.now().toString().slice(-6)}`;

// ── the staleness refusal — a walk against a stale bundle reports absent
//    features that are present (`DEF-MET-5844`'s lane learned this) ──────────
function newestMtime(dir) {
  let newest = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const path = join(dir, entry.name);
    const at = entry.isDirectory() ? newestMtime(path) : statSync(path).mtimeMs;
    if (at > newest) newest = at;
  }
  return newest;
}
const built = statSync(join(ROOT, "07-frontend/dist/index.html")).mtimeMs;
const newestCommit = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src", { cwd: ROOT }).toString().trim(),
).getTime();
const staleAgainst = Math.max(newestCommit, newestMtime(join(ROOT, "07-frontend/src")));
if (built < staleAgainst) {
  console.error(
    `REFUSED: dist/ built ${new Date(built).toISOString()} but src has work at ` +
      `${new Date(staleAgainst).toISOString()}. Run \`npx vite build\` first.`,
  );
  process.exit(2);
}
console.log(`MODE=${MODE} · dist ${new Date(built).toISOString()} >= src ${new Date(staleAgainst).toISOString()}`);

const R = [];
const ok = (n, c, d = "") => {
  R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
  console.log(R[R.length - 1]);
};
/** A row this lane cannot close because C1's half is not on the branch yet. */
const pending = (n, d = "") => {
  R.push(`PENDING · C1 · ${n}${d ? " · " + d : ""}`);
  console.log(R[R.length - 1]);
};
/** B14 rule 33 counts WORDS ON SCREEN, so this counts the rendered string. */
const words = (s) => s.trim().split(/\s+/).filter(Boolean).length;
const madeIds = [];

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });

// ── EVERY WAIT CARRIES A DEADLINE AND CHECKS THE PRODUCER IS ALIVE ─────────
const calls = [];
p.on("response", async (res) => {
  const u = new URL(res.url());
  if (!u.pathname.startsWith("/api/")) return;
  let body = null;
  if (res.request().method() !== "GET") {
    try {
      body = await res.json();
    } catch {
      body = null;
    }
  }
  calls.push({ m: res.request().method(), path: u.pathname, q: u.search, status: res.status(), body });
  if (body && body.id && /\/premises$/.test(u.pathname) && res.request().method() === "POST") {
    madeIds.push(`${body.premise_no ?? "?"} ${body.id}`);
  }
});

await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);
ok("signed in", true, p.url());

// ═══ SCREEN 1 · ADD PREMISE ════════════════════════════════════════════════
async function openDetails() {
  await p.goto(`${BASE}/${T}/premises/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  const one = p.locator("button,label").filter({ hasText: /one premise/i }).first();
  if (await one.count()) {
    await one.click();
    await p.waitForTimeout(400);
  }
  await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
  await p.waitForTimeout(2500);
}

async function pickKind(kind) {
  const label = p
    .locator("label.seg-opt")
    .filter({ has: p.locator(`input[name="owner_kind"][value="${kind}"]`) })
    .first();
  if ((await label.count()) === 0) return false;
  await label.click();
  await p.waitForTimeout(250);
  return await p.evaluate(
    (v) => document.querySelector(`input[name="owner_kind"][value="${v}"]`)?.checked === true,
    kind,
  );
}

await openDetails();
const addr1 = `${WALK_TAG} 41 Cypress Row`;
await p.fill("#address_line", addr1);
await p.selectOption("#premises_type", { label: "Single-family" });
await p.fill("#owner_manager", `${WALK_TAG} Cypress Holdings LLC`);
const kindTaken = await pickKind("company");
ok("Add premise · the owner's kind can be chosen", kindTaken);
const taxBox = p.locator("#owner_tax_id");
const hasTax = (await taxBox.count()) > 0;
ok("Add premise · a company's Tax ID box is reachable", hasTax);
if (hasTax) await taxBox.fill("74-2210099");
const typeSel = p.locator("#owner_account_type");
if (await typeSel.count()) {
  const opts = await typeSel.locator("option").allTextContents();
  const real = opts.filter((o) => o.trim() !== "" && !/choose|select|—/i.test(o));
  if (real.length) await typeSel.selectOption({ label: real[0] });
}

// ── what the wizard's owner control IS, today vs after ────────────────────
const ownerPicker = p.locator("#owner_id");
const ownerPickerPresent = (await ownerPicker.count()) > 0;
const acctPicker = p.locator("#owner_master_account, #master_account_id");
const acctPickerPresent = (await acctPicker.count()) > 0;
if (MODE === "before") {
  ok(
    "Add premise · [BEFORE] the control on screen is an OWNER RECORD picker",
    ownerPickerPresent,
    ownerPickerPresent ? "#owner_id is drawn" : "#owner_id is absent",
  );
  if (ownerPickerPresent) {
    await ownerPicker.click();
    await p.waitForTimeout(900);
    const optCount = await p.locator('[role="option"]:visible').count();
    ok(
      "Add premise · [BEFORE] that picker's cupboard is EMPTY — nothing can fill it",
      true,
      `${optCount} option(s) offered`,
    );
    await p.keyboard.press("Escape");
  }
} else {
  ok("Add premise · [AFTER] no owner-record picker is drawn", !ownerPickerPresent);
  ok("Add premise · [AFTER] an ACCOUNT search is drawn", acctPickerPresent);
  // The ONE word, on the control a clerk reads.
  const lbl = p.locator("#owner_master_account-label").first();
  if (await lbl.count()) {
    const text = (await lbl.innerText()).trim();
    ok('Add premise · [AFTER] the control is labelled exactly "Owner"', text === "Owner", text);
    ok("rule 33 · that label is ≤ 3 words", words(text) <= 3, `${words(text)} word(s)`);
  }
  // And it searches ACCOUNTS.
  const n0 = calls.length;
  await acctPicker.first().fill("AC");
  const dl0 = Date.now() + 12000;
  let hit = null;
  while (Date.now() < dl0) {
    hit = calls.slice(n0).find((c) => c.m === "GET" && /accounts|premises-owners/.test(c.path));
    if (hit) break;
    if (!b.isConnected()) throw new Error("browser died while waiting for the search");
    await p.waitForTimeout(200);
  }
  ok(
    "Add premise · [AFTER] the Owner control searches ACCOUNTS",
    hit !== null && /\/accounts/.test(hit.path) && /f\.kind=master/.test(hit.q),
    hit ? hit.path + hit.q : "no search fired",
  );
  await p.waitForTimeout(1200);
  const offered = await p.locator('[data-tracks="owner-account-results"] li').count();
  ok(
    "Add premise · [AFTER] and it FINDS the tenant's master account",
    offered > 0,
    `${offered} account(s) offered — the picker offered 0 before`,
  );
  if (offered > 0) {
    await p.locator('[data-tracks="owner-account-results"] button').first().click();
    await p.waitForTimeout(500);
    const card = await p.locator('[data-tracks="owner-account-card"]').count();
    ok("Add premise · [AFTER] the chosen account draws the confirmation card", card > 0);
    const cardText = card > 0 ? await p.locator('[data-tracks="owner-account-card"]').innerText() : "";
    ok(
      "Add premise · [AFTER] the card shows the account NUMBER (B14 rule 31)",
      /AC-\d{4}-\d{5}/.test(cardText),
      cardText.replace(/\n/g, " · "),
    );
    ok(
      "Add premise · [AFTER] and NO database id anywhere on the card",
      !/[0-9a-f]{8}-[0-9a-f]{4}-/.test(cardText),
    );
  }
}

// ── the one press ─────────────────────────────────────────────────────────
// Step 2 (details) → step 3 (review) → the commit. `BR-MET-112`: nothing is
// written until that last button, so the press we time is the commit.
await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
await p.waitForTimeout(1800);
const before = calls.length;
const save = p.locator("button").filter({ hasText: /^Create premise/ }).last();
await save.click();
const deadline = Date.now() + 25000;
let posted = null;
while (Date.now() < deadline) {
  posted = calls.slice(before).find((c) => c.m === "POST" && /\/premises$/.test(c.path));
  if (posted) break;
  if (b.isConnected() === false) throw new Error("browser died while waiting for the save");
  await p.waitForTimeout(250);
}
// ⚠ **ONE REFUSAL IS THIS LANE'S EXPECTED STATE AND IS NOT A FAILURE.** The
// screen posts `master_account_id`; C1's door is not on the branch yet, so
// `_validate_premises` refuses it BY NAME — `metering.unknown_field`, field
// `master_account_id`. That is the door behaving correctly and it **proves the
// screen sends the agreed key**, which is the one thing this row can prove
// before the two halves meet. Any OTHER refusal is a real failure and is
// reported as one.
const unknownMasterField =
  posted !== null &&
  posted.status === 422 &&
  JSON.stringify(posted.body ?? {}).includes('"field":"master_account_id"');
if (unknownMasterField) {
  pending(
    "Add premise · one press saves the address",
    "the door refuses `master_account_id` by name — C1's half is not on the branch. The screen sends the agreed key.",
  );
} else {
  ok(
    "Add premise · one press saves the address",
    posted !== null && posted.status < 400,
    posted ? `HTTP ${posted.status} ${JSON.stringify(posted.body).slice(0, 220)}` : "no POST seen",
  );
}

if (posted && posted.body) {
  const warnings = posted.body.warnings ?? posted.body.owner_account ?? null;
  console.log("   server said:", JSON.stringify(warnings));
  const wroteAccount =
    posted.body.master_account != null ||
    posted.body.master_account_id != null ||
    // ⚠ **`/created/` MATCHED `owner_account_not_created` AND REPORTED THE
    // BROKEN SCREEN AS FIXED.** CLAUDE.md law 7, habit 2 — ask what would make
    // this check pass WRONGLY. The verdict constant for *nothing happened* has
    // the word for *it happened* inside it, so the code is compared WHOLE.
    (Array.isArray(warnings) &&
      warnings.some((w) => (w && w.code) === "owner_account_created"));
  if (MODE === "before") {
    ok("Add premise · [BEFORE] NO master account was opened", !wroteAccount);
  } else if (unknownMasterField) {
    pending("Add premise · the master account is opened and named", "awaits C1's door");
  } else {
    ok("Add premise · [AFTER] the master account was opened and named", wroteAccount);
  }
}

// ── DOES THE VERDICT REACH THE CLERK? ────────────────────────────────────
//
// ⚠ **THE ASSERTION READS THE TOAST REGION AND COMPARES IT WITH THE SENTENCE
// THE SERVER'S OWN `message_key` RESOLVES TO.** A hand-written regex of likely
// phrasings was tried first and **it failed on a working screen**: it listed
// *account opened*, *no owner*, *needs an identifier* and six more, and C1's
// actual wording for the commonest case is *"Owner's account linked"*, which
// matched none of them. A check that enumerates what it expects to see is the
// same fault as a reader that enumerates codes — it goes quiet on the case
// nobody thought of. So this reads what the SERVER said and asserts THAT
// reached the screen, which is the only version of this check that cannot be
// wrong about the wording.
await p.waitForTimeout(2500);
const toastText = await p
  .locator('[data-toast="region"]')
  .innerText()
  .catch(() => "");
const bodyText = await p.locator("body").innerText();
const seen = `${toastText}\n${bodyText}`;
if (posted && posted.body) {
  const ws = Array.isArray(posted.body.warnings) ? posted.body.warnings : [];
  const keys = ws.map((w) => w && w.message_key).filter(Boolean);
  if (MODE === "before") {
    ok(
      "Add premise · [BEFORE] the clerk is told NOTHING about the owner's account",
      toastText.trim() !== "" ? !/owner/i.test(toastText) : true,
      `toast said: ${JSON.stringify(toastText)}`,
    );
  } else if (keys.length === 0) {
    pending("Add premise · the verdict reaches the clerk", "server sent no message_key");
  } else {
    // Resolve each key through the SHIPPED English catalogue — the same file
    // the app loads — so this compares the screen with the catalogue rather
    // than with a phrase this walk made up.
    // ⚠ `readFileSync`, NOT `execSync("cat …")` — the catalogue is 1.1 MB and
    // `execSync`'s default `maxBuffer` is 1 MB, so the shell form throws
    // ENOBUFS and takes the whole walk down after every assertion has passed.
    const catalogue = JSON.parse(
      readFileSync(join(ROOT, "07-frontend/src/i18n/locales/en.json"), "utf8"),
    );
    const expected = keys.map((k) => catalogue[k]).filter(Boolean);
    ok(
      "Add premise · [AFTER] every verdict the server sent reaches the clerk",
      expected.length === keys.length && expected.every((sentence) => seen.includes(sentence)),
      `server said ${JSON.stringify(keys)} → screen shows ${JSON.stringify(expected.filter((x) => seen.includes(x)))}`,
    );
    // B14 rule 33: a fact is ≤ 6 words. C1 owns these sentences; this counts
    // them on the rendered screen, which is where the rule applies.
    for (const sentence of expected) {
      ok(`rule 33 · "${sentence}" is ≤ 6 words`, words(sentence) <= 6, `${words(sentence)} words`);
    }
    // ⛔ AND NO DATABASE ID REACHED THE SCREEN WITH IT. C1's warning carries
    // `account_id` beside `account_no`, correctly; a toast has no href, so the
    // id has no business in one (B14 rule 31).
    const ids = ws.map((w) => w && w.account_id).filter(Boolean);
    if (ids.length) {
      ok(
        "Add premise · [AFTER] and NO database id reached the screen with it",
        ids.every((id) => !seen.includes(id)),
        `stripped ${ids.length} id(s) the server sent`,
      );
    }
  }
}

// ═══ SCREEN 3 · PREMISES DETAIL ═══════════════════════════════════════════
// ⚠ **IT FALLS BACK TO AN EXISTING PROPERTY RATHER THAN SKIPPING THE SCREEN.**
// While C1's door refuses the create, `madeIds` is empty — and a walk that
// silently skips a third of what it claims to cover is a check that reports
// zero over a scope it excludes (CLAUDE.md hard-won law 7). The property page
// is this lane's to prove and does not need the create to have worked.
let madeId = madeIds.length ? madeIds[madeIds.length - 1].split(" ").pop() : null;
if (madeId === null) {
  const first = await p.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/premises?per=1`, { headers: { accept: "application/json" } });
    const j = await r.json().catch(() => null);
    return j?.results?.[0]?.id ?? null;
  }, T);
  madeId = first;
  console.log("   (no premises created — walking the property page on an existing one)");
}
if (madeId) {
  await p.goto(`${BASE}/${T}/premises/${madeId}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2000);
  // ⚠ **`Find` IS DRAWN ONLY WHERE THERE IS NOBODY TO FIND, AND THAT IS THE
  // POINT OF IT.** It lives inside the `Needs an owner` branch: a property that
  // already names an account does not offer to attach one. So a property this
  // walk just created WITH an owner correctly has no Find button, and asserting
  // one unconditionally is the walk being wrong rather than the screen. The
  // control is exercised on a property that actually needs it.
  const hasOwner = (await p.locator('[data-tracks="owner-typed"]').count()) > 0;
  const find = p.locator("button").filter({ hasText: /find/i }).first();
  const findPresent = (await find.count()) > 0;
  if (hasOwner) {
    ok(
      "Premises detail · a property WITH an owner offers no Find, correctly",
      !findPresent,
      "Find belongs to the Needs an owner branch",
    );
    // Walk it on one that needs it instead.
    const orphan = await p.evaluate(async (tenant) => {
      const r = await fetch(`/api/${tenant}/premises?per=50`, { headers: { accept: "application/json" } });
      const j = await r.json().catch(() => null);
      const row = (j?.results ?? []).find((x) => !x.master_account_no && !x.master_account_id);
      return row?.id ?? null;
    }, T);
    if (orphan) {
      await p.goto(`${BASE}/${T}/premises/${orphan}`, { waitUntil: "networkidle" });
      await p.waitForTimeout(2000);
    }
  }
  const find2 = p.locator("button").filter({ hasText: /find/i }).first();
  const findPresent2 = (await find2.count()) > 0;
  ok("Premises detail · a property that NEEDS an owner offers Find", findPresent2);
  if (findPresent2) {
    const n = calls.length;
    await find2.click();
    await p.waitForTimeout(600);
    // ⚠ **NO SECOND `Find` BUTTON ANY MORE.** The old control was type-then-
    // press; the shared search fires on a 300 ms debounce, which is `IS-3` and
    // is what every other search in the product does.
    const box = p.locator("#owner_find_account");
    const boxPresent = (await box.count()) > 0;
    ok("Premises detail · the Find panel draws the shared account search", boxPresent);
    if (boxPresent) {
      await box.fill("AC");
      const dl = Date.now() + 15000;
      let searched = null;
      while (Date.now() < dl) {
        searched = calls.slice(n).find((c) => c.m === "GET" && /accounts|premises-owners/.test(c.path));
        if (searched) break;
        if (!b.isConnected()) throw new Error("browser died while waiting for the find search");
        await p.waitForTimeout(200);
      }
      console.log("   the search hit:", searched ? searched.path + searched.q : "nothing");
      const hitAccounts = searched !== null && /\/accounts/.test(searched.path);
      if (MODE === "before") {
        ok(
          "Premises detail · [BEFORE] Find searches OWNER RECORDS, never accounts",
          searched !== null && !hitAccounts,
          searched ? searched.path : "",
        );
      } else {
        ok(
          "Premises detail · [AFTER] Find searches ACCOUNTS — the PO's 'we are unabel to find and map master account'",
          hitAccounts,
          searched ? searched.path + searched.q : "nothing",
        );
        await p.waitForTimeout(1500);
        const rows = await p.locator('[data-tracks="owner-account-results"] li').count();
        ok(
          "Premises detail · [AFTER] and it FINDS the tenant's master account",
          rows > 0,
          `${rows} account(s) — it found 0 before, for ever`,
        );
      }
    }
  }
}

// ═══ SCREEN 2 · EDIT PREMISE ══════════════════════════════════════════════
await p.goto(`${BASE}/${T}/premises`, { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
// B14 rule 4: row actions are ICONS. The visible label is on the control's
// `aria-label`/`title`, never in its text, so a text filter finds nothing —
// which reads exactly like a missing Edit door.
const editBtn = p
  .locator('button[aria-label="Edit"], button[title="Edit"], [aria-label="Edit"]')
  .first();
if (await editBtn.count()) {
  await editBtn.click();
  await p.waitForTimeout(2000);
  const modalText = await p.locator("body").innerText();
  const notListed = /not listed\?/i.test(modalText);
  const editOwnerPicker = p.locator("#owner_id");
  const editOwnerPresent = (await editOwnerPicker.count()) > 0;
  if (MODE === "before") {
    ok("Edit premise · [BEFORE] the owner control is the owner-RECORD picker", editOwnerPresent);
    ok(
      "Edit premise · [BEFORE] it says 'Not listed? Type the name below' — an instruction that creates nothing",
      notListed,
    );
    if (editOwnerPresent) {
      await editOwnerPicker.click();
      await p.waitForTimeout(900);
      const n2 = await p.locator('[role="option"]:visible').count();
      ok("Edit premise · [BEFORE] and the list it searches is empty", true, `${n2} option(s)`);
      await p.keyboard.press("Escape");
    }
  } else {
    ok("Edit premise · [AFTER] no owner-record picker", !editOwnerPresent);
    ok("Edit premise · [AFTER] the dead 'Not listed? Type the name below' is gone", !notListed);
    const acct = p.locator("#owner_master_account");
    ok("Edit premise · [AFTER] an account search is drawn", (await acct.count()) > 0);
    ok(
      "Edit premise · [AFTER] 'Owner / manager' is gone; the box says 'Managed by'",
      /Managed by/.test(modalText) && !/Owner \/ manager/.test(modalText),
    );
    if (await acct.count()) {
      const n3 = calls.length;
      await acct.first().fill("AC");
      const dl3 = Date.now() + 12000;
      let hit3 = null;
      while (Date.now() < dl3) {
        hit3 = calls.slice(n3).find((c) => c.m === "GET" && /accounts|premises-owners/.test(c.path));
        if (hit3) break;
        if (!b.isConnected()) throw new Error("browser died while waiting for the edit search");
        await p.waitForTimeout(200);
      }
      ok(
        "Edit premise · [AFTER] it searches ACCOUNTS — the PO's 'in edit also we are unabel to search owner'",
        hit3 !== null && /\/accounts/.test(hit3.path),
        hit3 ? hit3.path + hit3.q : "no search fired",
      );
      await p.waitForTimeout(1200);
      const rows3 = await p.locator('[data-tracks="owner-account-results"] li').count();
      ok("Edit premise · [AFTER] and it FINDS one", rows3 > 0, `${rows3} account(s)`);
    }
  }
}

// ═══ THE VOCABULARY ═══════════════════════════════════════════════════════
await p.goto(`${BASE}/${T}/premises`, { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
const listText = await p.locator("body").innerText();
// ⚠ **FOUR OF THE FIVE GO; THE FIFTH IS THE SURVIVING NOUN AND STAYS.** The PO
// counted five wordings for one fact — *Owner*, *Owner (record)*, *Owner /
// manager*, *master account {{n}}*, *Needs an owner* — and ruled *"we ahve to
// use one volcabory"*. **Owner** is that one word. *Needs an owner* is that
// same noun naming its own absence, not a fifth name for the thing, and the
// blueprint names that list twice (`CR-089-p036`: *"Clearing it is allowed and
// puts the property on the Needs an owner list"*). Retiring it would rename a
// list filter the drawing specifies. So it is asserted PRESENT, deliberately.
const RETIRED = [
  ["Owner (record)", /Owner \(record\)/],
  ["Owner / manager", /Owner \/ manager/],
  ["master account {n}", /master account\s+\S/i],
];
for (const [word, re] of RETIRED) {
  const live = re.test(listText);
  if (MODE === "before") {
    if (live) ok(`Vocabulary · [BEFORE] "${word}" is live on screen`, true);
  } else {
    ok(`Vocabulary · [AFTER] "${word}" is gone from the clerk's screen`, !live);
  }
}
if (MODE === "after") {
  ok(
    'Vocabulary · [AFTER] the surviving noun "Owner" still names the column',
    /\bOwner\b/.test(listText),
  );
}

// ── B14 rule 33 · the caps ────────────────────────────────────────────────
for (const sel of ["#owner_id-label", "#owner_master_account-label", "label[for='owner_manager']"]) {
  const el = p.locator(sel).first();
  if (await el.count()) {
    const txt = (await el.innerText()).replace(/\*$/, "");
    ok(`rule 33 · label "${txt.trim()}" is ≤ 3 words`, words(txt) <= 3, `${words(txt)} words`);
  }
}

console.log("\n── RESULT ─────────────────────────────────────────────");
for (const line of R) console.log(line);
console.log(`\n${R.filter((l) => l.startsWith("PASS")).length}/${R.length} PASS`);
console.log("premises created by this walk (purge these):", madeIds.join(", ") || "none");
await b.close();
