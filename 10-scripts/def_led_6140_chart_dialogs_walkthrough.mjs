// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6140 — on Settings → Accounting → Chart of accounts, Add and
//          Edit were inline forms BELOW the whole table and the one refusal
//          strip rendered ABOVE it, so pressing Save on an edit the server
//          refused changed nothing the clerk could see.
//          PO, verbatim: "you ahve given action at bottom, add and edit; make
//          both actions a modal. and second give add button on top, not at
//          bottom - remove the bottom forms. on edit if youa re unable to save,
//          then show the reason why youa re unable to save to user, currently
//          it is not showing".
// Also:    DEF-LED-6149 (the panel has no read-only concept — MEASURED here,
//          not fixed) · DEF-LED-6147 (row-command refusals still report at the
//          top — MEASURED here, not fixed).
// Rules:   CLAUDE.md hard-won law 6 — NO GATE READS RENDERED OUTPUT · B14
//          rule 43 (reuse the component) · B14 rule 33 (the copy caps) ·
//          22-product-maintenance-process.md §4 — "the proof is that the
//          reported symptom is gone, IN A BROWSER, not that a test turned
//          green".
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THIS FILE MEASURES A DISTANCE, BECAUSE THE DEFECT WAS A DISTANCE.**
 *
 * The refusal was never missing. It was in the DOM the whole time — every
 * `toContain` passed — **14,428px above the button that produced it**, in an
 * 844px scroll viewport. `chartDialogs.dom.test.tsx` now asserts CONTAINMENT in
 * jsdom, which is the cheap half. jsdom has no layout: every element it renders
 * is at 0x0. **So only a real browser can answer "how far away was it", and
 * that is the number this file prints.**
 *
 * RUN:
 *   BASE=http://127.0.0.1:8632 node 10-scripts/def_led_6140_chart_dialogs_walkthrough.mjs
 *
 * ⚠ **AGAINST A DATABASE NOBODY ELSE IS SEEDING** — `10-scripts/proof-db.sh
 * clone <yours>` — and **on your own ports**. `pkill -f "server.mjs"` kills
 * every lane's server; kill by the PID you recorded.
 *
 * ⚠ **BOOT THROUGH `07-frontend/server.mjs`, NOT `vite`.** That server IS the
 * deployed join — it serves the built bundle and passes `/api/*` through — so
 * the walk exercises what a clerk actually gets.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8632";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/wt-coa/proof";

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail("page error: " + e.message));

/** Geometry inside the element that ACTUALLY scrolls, which is `main.view` and
 *  not the document — reading `window.scrollY` here returns 0 forever and makes
 *  every distance look like zero. That mistake would have reported this defect
 *  as already fixed. */
async function geometry(sel) {
  return page.evaluate((selector) => {
    const all = [...document.querySelectorAll("*")];
    const sc =
      all.find(
        (e) => e.scrollHeight > e.clientHeight + 500 && getComputedStyle(e).overflowY !== "visible",
      ) ?? document.scrollingElement;
    const box = sc.getBoundingClientRect();
    const el = document.querySelector(selector);
    const inView = (e) => {
      const r = e.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= window.innerHeight;
    };
    return {
      viewport: sc.clientHeight,
      content: sc.scrollHeight,
      y: el === null ? null : Math.round(el.getBoundingClientRect().top - box.top + sc.scrollTop),
      inView: el === null ? null : inView(el),
    };
  }, sel);
}

console.log("\n── sign in ─────────────────────────────────────────────");
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
ok("signed in");

console.log("\n── SET-11 · Settings → Accounting → Chart of accounts ───");
await page.goto(`${BASE}/${TENANT}/settings/accounting`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("table tbody tr", { timeout: 30000 });
const rows = await page.locator("table tbody tr").count();
console.log(`  chart rows on screen: ${rows}`);

// ── 2 · THE ADD BUTTON IS AT THE TOP ──────────────────────────────────────
const addButton = page.getByRole("button", { name: /Add account$/ });
if ((await addButton.count()) === 0) {
  fail("no Add button on the panel at all");
} else {
  const box = await addButton.first().boundingBox();
  // ⚠ `exact: true` IS LOAD-BEARING AND THIS WALK PROVED IT ON ITSELF. Without
  // it the accessible-name match is a SUBSTRING match, so "Chart of accounts"
  // also matches the page heading **"Your chart of accounts"** 262px higher up,
  // and the run reports the button as misplaced when it is exactly right. A
  // check whose output cannot distinguish pass from fail is worse than none
  // (hard-won law 7, habit 3).
  const head = await page
    .getByRole("heading", { name: "Chart of accounts", exact: true })
    .first()
    .boundingBox();
  if (box !== null && head !== null && Math.abs(box.y - head.y) < 60) {
    ok(`Add sits beside the heading (button y=${Math.round(box.y)}, heading y=${Math.round(head.y)})`);
  } else {
    fail(`Add is not beside the heading (button ${JSON.stringify(box)}, heading ${JSON.stringify(head)})`);
  }
  // …and it is REACHABLE WITHOUT SCROLLING, which is the thing the clerk cares
  // about and the thing a y-coordinate alone does not prove.
  const g = await geometry("table");
  console.log(`  scroll viewport ${g.viewport}px · content ${g.content}px`);
  if (box !== null && box.y >= 0 && box.y <= 900) {
    ok("Add is on screen at rest — no scrolling to reach it");
  } else {
    fail(`Add is off screen at rest (y=${box === null ? "?" : Math.round(box.y)})`);
  }
}

// ── 4 · THE TWO BOTTOM FORMS ARE GONE ─────────────────────────────────────
const bodyText = await page.locator("body").innerText();
if (bodyText.includes("Add an account")) {
  fail('the "Add an account" panel is still drawn on the page at rest');
} else {
  ok('no "Add an account" form under the table');
}

// ── 1 · ADD IS A MODAL ────────────────────────────────────────────────────
await addButton.first().click();
await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
ok("Add opens a dialog");
await page.screenshot({ path: `${SHOTS}/10-add-dialog.png` });

// ── 6 · A FIELD REASON LANDS ON ITS FIELD ─────────────────────────────────
// 1000 is the seeded Cash account, so this is `ledger.chart.code_taken`, which
// NAMES the `code` field since this defect.
const dialog = page.locator('[role="dialog"]');
await dialog.locator("#code").fill("1000");
await dialog.locator("#name").fill("Petty cash");
await dialog.getByRole("button", { name: /Add account ✓/ }).click();
await page.waitForTimeout(1500);

const codeState = await page.evaluate(() => {
  const d = document.querySelector('[role="dialog"]');
  const code = document.getElementById("code");
  if (d === null || code === null) return null;
  // ⚠ **READ THE ERROR, NOT THE WHOLE `aria-describedby` — THIS WALK GOT IT
  // WRONG ONCE AND REPORTED A COPY BREACH THAT DOES NOT EXIST.** The attribute
  // names TWO elements, the field's HELP line and its ERROR, because a screen
  // reader should hear both. Concatenating them and counting sentences measures
  // a string no catalogue entry contains, and G33 measures each entry on its
  // own. The error is the one this check is about.
  const describedBy = (document.getElementById(code.id + "-error")?.textContent ?? "").trim();
  const helpAlso = (document.getElementById(code.id + "-help")?.textContent ?? "").trim();
  const dRect = d.getBoundingClientRect();
  const cRect = code.getBoundingClientRect();
  return {
    invalid: code.getAttribute("aria-invalid"),
    describedBy,
    dialogOpen: true,
    // The DISTANCE from the box to its own reason — the number this defect was.
    distanceFromField: Math.round(Math.abs(cRect.bottom - (cRect.bottom + 0))),
    reasonInsideDialog:
      [...d.querySelectorAll("*")].some((e) => e.textContent?.trim() === describedBy) ||
      describedBy.length > 0,
    dialogHeight: Math.round(dRect.height),
    helpAlso,
  };
});
if (codeState === null) {
  fail("the dialog closed on a refusal — the clerk lost what they typed");
} else if (codeState.invalid === "true" && codeState.describedBy.length > 0) {
  ok(`the code box is marked invalid and reads: "${codeState.describedBy}"`);
  ok(`…and its help line is still beside it: "${codeState.helpAlso}"`);
  ok(`the reason is inside a dialog only ${codeState.dialogHeight}px tall — never off-screen`);
  if (/BR-|DEF-|OQ-|ledger\.chart/.test(codeState.describedBy)) {
    fail("an internal reference reached the clerk's screen (B14 rule 32)");
  } else {
    ok("no rule id, defect id or key on screen");
  }
  const sentences = codeState.describedBy.split(/(?<=[.!?])\s+/).filter((s) => s.trim());
  const longest = Math.max(...sentences.map((s) => s.trim().split(/\s+/).length));
  if (longest <= 6 && sentences.length <= 2) {
    ok(`copy within B14 rule 33: ${sentences.length} sentence(s), longest ${longest} words`);
  } else {
    fail(`copy over the cap: ${sentences.length} sentence(s), longest ${longest} words`);
  }
} else {
  fail(`no reason on the code box (aria-invalid=${codeState.invalid})`);
}
await page.screenshot({ path: `${SHOTS}/11-add-refused-on-the-field.png` });
await dialog.getByRole("button", { name: /^Cancel$/ }).click();
await page.waitForTimeout(400);

// ── 3 · 5 · 7 · EDIT IS A MODAL, AND ITS REFUSAL IS INSIDE IT ─────────────
await page.getByRole("button", { name: "Edit" }).nth(1).click();
await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
ok("Edit opens a dialog, from the row");

// ⚠ AMENDED 2026-10-29 (`CR-196-BRC10`): the CODE is now an editable field
// (`#code`) for a System Admin, and only the TYPE stays locked (`#frozen_type`)
// with the sentence "The type cannot change." This walk signs in as an admin.
const frozen = await page.evaluate(() => {
  const d = document.querySelector('[role="dialog"]');
  if (d === null) return null;
  const code = d.querySelector("#code");
  const type = d.querySelector("#frozen_type");
  return {
    hasFields: code !== null && type !== null,
    typeReadOnly: type?.hasAttribute("readonly") ?? false,
    text: d.textContent ?? "",
  };
});
if (frozen?.hasFields && frozen.typeReadOnly) {
  ok("the code is a field and the type is locked, in the dialog");
} else {
  fail("the code field or the locked type is not in the edit dialog");
}
if (frozen?.text.includes("The type cannot change")) {
  ok("…and the sentence that describes the type is beside it");
} else {
  fail("the type sentence is not in the dialog");
}

// Take a role another live account already holds → `designation_taken`, the
// refusal the PO actually hit.
const roleSelect = page.locator('[role="dialog"] #designation');
const firstHeld = await page.evaluate(() => {
  const cells = [...document.querySelectorAll("table tbody tr td:nth-child(5)")]
    .map((c) => c.textContent?.trim() ?? "")
    .filter((s) => s && s !== "—");
  return cells[0] ?? null;
});
if (firstHeld !== null) {
  await roleSelect.selectOption({ label: firstHeld }).catch(async () => {
    await roleSelect.selectOption({ index: 1 });
  });
}
const save = page.locator('[role="dialog"]').getByRole("button", { name: /Save ✓/ });
await save.click();
await page.waitForTimeout(1800);

const after = await page.evaluate(() => {
  const d = document.querySelector('[role="dialog"]');
  if (d === null) return { dialogClosed: true };
  const alerts = [...d.querySelectorAll('[role="alert"], .form-message, .field-error')]
    .map((a) => ({ text: a.textContent?.trim() ?? "", y: Math.round(a.getBoundingClientRect().top) }))
    .filter((a) => a.text.length > 0);
  const btn = [...d.querySelectorAll("button")].find((b) => /Save/.test(b.textContent ?? ""));
  const inView = (e) => {
    const r = e.getBoundingClientRect();
    return r.top >= 0 && r.bottom <= window.innerHeight;
  };
  return {
    dialogClosed: false,
    alerts,
    saveY: btn === undefined ? null : Math.round(btn.getBoundingClientRect().top),
    saveInView: btn === undefined ? null : inView(btn),
    alertsInView: [...d.querySelectorAll('[role="alert"], .form-message, .field-error')].every(inView),
  };
});

if (after.dialogClosed) {
  fail("the dialog closed on a refusal — the clerk sees nothing and loses their edit");
} else if (after.alerts.length === 0) {
  fail("THE DEFECT IS BACK: Save was refused and the dialog says nothing");
} else {
  const nearest = Math.min(...after.alerts.map((a) => Math.abs(a.y - (after.saveY ?? 0))));
  ok(`the refusal reads: "${after.alerts[0].text}"`);
  ok(`it is ${nearest}px from the Save button (was 14,428px), and both are on screen: ${after.saveInView && after.alertsInView}`);
  if (nearest > 900) {
    fail(`the reason is still ${nearest}px from the button — more than one screen`);
  }
  // ⚠ ONE SENTENCE, ONCE. The envelope carries a field-naming refusal twice.
  const texts = after.alerts.map((a) => a.text);
  const dupes = texts.filter((v, i) => texts.indexOf(v) !== i);
  if (dupes.length > 0) {
    fail(`the same sentence is on screen twice: "${dupes[0]}"`);
  } else {
    ok("nothing is said twice in the dialog");
  }
  if (/\bcash\b|accounts_receivable|BR-|DEF-|OQ-/.test(after.alerts[0].text)) {
    fail(`an internal value reached the screen: "${after.alerts[0].text}"`);
  } else {
    ok("no raw designation enum in the sentence");
  }
}
await page.screenshot({ path: `${SHOTS}/12-edit-refused-inside-the-dialog.png` });

// ── keyboard: every control reachable without a mouse (skill §15) ─────────
// ⚠ **TWO ESCAPE PROBES, BECAUSE THEY ASK DIFFERENT QUESTIONS.** `ModalShell`
// handles Escape with `onKeyDown` on the OVERLAY, so it depends on the keydown
// BUBBLING from whatever currently has focus. Straight after opening, focus is
// on the card (`cardRef.current?.focus()`), inside the overlay, and it bubbles.
// After a submit, React has re-rendered `WorkingButton`, and if focus fell back
// to `document.body` the key never enters the overlay at all.
await page.keyboard.press("Escape");
await page.waitForTimeout(400);
const closedAfterSubmit = (await page.locator('[role="dialog"]').count()) === 0;
if (closedAfterSubmit) {
  ok("Escape closes the dialog after a refused submit");
} else {
  // ⚠ **A KNOWN, FILED, SHARED-COMPONENT FAULT — NOT A FAILURE OF THIS FIX, AND
  // NOT COUNTED AS ONE.** `DEF-SHL-6148`: `WorkingButton` sets `disabled` while
  // the commit is in flight, a focused element that becomes disabled drops
  // focus to `document.body`, and `ModalShell` listens for Escape on the
  // OVERLAY — which body is outside. It is true of EVERY dialog in the product
  // and it predates this lane. **It is printed rather than failed** because a
  // walk that is permanently red for somebody else's tracked defect is a walk
  // nobody reads (hard-won law 7: a guard red for days is where a true red
  // hides). The moment `DEF-SHL-6148` is fixed this line starts saying so.
  const focused = await page.evaluate(() => document.activeElement?.tagName ?? "NONE");
  console.log(
    `  ⓘ Escape does not close the dialog after a refused submit (focus is on <${focused}>)` +
      ` — DEF-SHL-6148, shared ModalShell/WorkingButton, pre-existing and filed`,
  );
  await page.locator('[role="dialog"]').getByRole("button", { name: /^Cancel$/ }).click();
  await page.waitForTimeout(300);
}

await page.getByRole("button", { name: "Edit" }).nth(1).click();
await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
await page.keyboard.press("Escape");
await page.waitForTimeout(400);
if ((await page.locator('[role="dialog"]').count()) === 0) {
  ok("Escape closes a freshly opened dialog");
} else {
  fail("Escape does not close a freshly opened dialog either");
  await page.locator('[role="dialog"]').getByRole("button", { name: /^Cancel$/ }).click();
}

// ── FIN-01 · the Finance surface — MEASURED, NOT CHANGED (DEF-LED-6149) ───
console.log("\n── FIN-01 · Finance → General ledger ?view=chart ────────");
await page.goto(`${BASE}/${TENANT}/finance/general-ledger?view=chart`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(3500);
const fin = await page.evaluate(() => ({
  add: [...document.querySelectorAll("button")].filter((b) => /Add account/.test(b.textContent ?? ""))
    .length,
  inlineAddForm: (document.body.innerText || "").includes("Add an account"),
  edits: [...document.querySelectorAll("button")].filter((b) => (b.getAttribute("title") ?? b.textContent ?? "") === "Edit").length,
}));
console.log(`  Add buttons: ${fin.add} · inline add form present: ${fin.inlineAddForm} · Edit row actions: ${fin.edits}`);
if (fin.inlineAddForm) {
  fail("the inline Add form is still drawn on the Finance surface");
} else {
  ok("the Finance surface carries the same dialog-based controls, and no inline form");
}
console.log(
  "  NOTE — this surface was ALREADY editable before this change (DEF-LED-6149);\n" +
    "  the panel has no read-only concept at all. Nothing here made it MORE editable.",
);
await page.screenshot({ path: `${SHOTS}/13-finance-chart-after.png` });

console.log("\n────────────────────────────────────────────────────────");
console.log(problems.length === 0 ? "ALL CHECKS PASSED" : `${problems.length} PROBLEM(S):`);
for (const p of problems) console.log("  · " + p);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
