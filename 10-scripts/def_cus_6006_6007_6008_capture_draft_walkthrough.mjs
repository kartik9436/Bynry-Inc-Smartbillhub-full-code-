// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-6006 (the draft minimum) · DEF-CUS-6007 (the form grid and
//           its rhythm) · DEF-CUS-6008 (the NOT NULL address this walk FOUND).
// Rules:    B14 rule 33 (an INSTRUCTION caps at six words per sentence;
//           RATIONALE is zero words on screen) · rule 38 (where a drawing and
//           our UI rules disagree about how a FORM IS BUILT, the UI rules win)
//           · rule 39 (one spacing scale; field → field 20px) · rule 40 (the
//           page-head title is 32px) · BR-CUS-070 (the address is verbatim and
//           immutable AFTER CAPTURE — implemented as after the row leaves
//           DRAFT) · BR-CUS-091 (a staff-raised request needs no applicant) ·
//           BR-CUS-093 (numbered at creation).
// ───────────────────────────────────────────────────────
//
// THE BROWSER WALK FOR REQ-03's CAPTURE STEP 1 — hard-won law 6, the one law
// with no tool. No gate in this repo reads rendered output, and B14 rule 39's
// own status cell says the 5/6/20 figures "have no gate and are readable only
// through a browser instrument". Every claim this lane makes about a pixel, a
// disabled control or a stored value is a claim only this script can check.
//
// ⚠ **IT EARNED ITS KEEP ON THE FIRST RUN.** `DEF-CUS-6008` — `POST
// /service-requests` answering 500 with `NotNullViolation` on
// `address_as_given` — was live on the branch while `tsc`, 96 frontend cases,
// 116 backend cases and every gate were green. Eight new backend cases passed
// over it because each OMITTED the key and Django's `TextField` default hid the
// difference; the SCREEN never omits it. A clerk met it on the first press of
// Save as draft.
//
// HOW TO RUN IT (the stack is the DEPLOYED join, not the dev server — the vite
// dev server has no /api proxy and cannot serve this app same-origin):
//
//   cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \
//     .venv/bin/python manage.py runserver 127.0.0.1:8101 --noreload --skip-checks &
//   cd 07-frontend && npx vite build \
//     && PORT=8181 API_PROXY_TARGET=http://127.0.0.1:8101 node server.mjs &
//   WALK_BASE=http://127.0.0.1:8181 node 10-scripts/def_cus_6006_6007_6008_capture_draft_walkthrough.mjs
//
// ⚠ **REACH STEP 3 BY WALKING THE WIZARD, NEVER BY RELOADING AT
// `?request=…&step=3`.** The capture wizard deliberately never hydrates from
// the fetched draft — `ServiceRequestCapturePage.tsx` says so where the SSN is
// built, because the read path returns `ssn_last4` only and rehydrating would
// send `""` and ERASE a stored number. So a resume-by-URL lands on an EMPTY
// form and `Save as draft` is correctly disabled. A first draft of this script
// tested that and reported a failure that was not one.
//
// WHAT IT PRINTS: one PASS/FAIL line per claim, then any page error or 5xx,
// then a count. It distinguishes pass from fail TO A READER and not merely by
// an exit code (hard-won law 7 habit 3).
// The browser walk for DEF-CUS-6006 (the draft minimum) and DEF-CUS-6007 (the
// form grid). No gate in this repo reads rendered output, so this is the only
// instrument that can see either fix (hard-won law 6).
import { createRequire } from "node:module";
// `playwright-core` lives in `07-frontend/node_modules`, and this script sits in
// `10-scripts/` — the same resolution 12-smoke-walkthrough.mjs uses.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

// The repo's own resolver (10-scripts/12-smoke-walkthrough.mjs): the pinned
// revision is usually absent here and an off-revision chromium beats not
// running at all — the mismatch is printed so nobody is surprised.
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const c = join(root, dir, sub);
        if (existsSync(c)) { console.log(`chromium: using ${c}`); return c; }
      }
    }
  }
  throw new Error("no chromium found");
}

const BASE = process.env.WALK_BASE ?? "http://127.0.0.1:8181";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd";
const out = [];
const say = (ok, what, detail = "") =>
  out.push(`${ok ? "PASS" : "FAIL"}  ${what}${detail ? " — " + detail : ""}`);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("response", (r) => { if (r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });
  say(true, "signed in as the seeded owner");

  // ── 1 · STEP 1, NOTHING TYPED ────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/requests/new?step=1`, { waitUntil: "networkidle" });
  await page.waitForSelector("h1", { timeout: 20000 });
  const save = page.getByRole("button", { name: "Save as draft" });
  say(await save.isDisabled(), "step 1, nothing typed: Save as draft is disabled");
  const note = page.locator("#capture-draft-blocked");
  const noteText = (await note.count()) ? (await note.innerText()).trim() : "(absent)";
  say(noteText === "Enter the name first.",
      "the short message is VISIBLE TEXT on screen", JSON.stringify(noteText));
  say(await note.isVisible(), "…and it is actually visible, not sr-only");
  say((await save.getAttribute("title")) === null,
      "Save as draft carries NO title attribute any more");
  say((await save.getAttribute("aria-describedby")) === "capture-draft-blocked",
      "the button points at the note with aria-describedby");
  // Keyboard reach: the note is in the normal flow above the button, so a
  // keyboard user meets it without hover. Prove it is in the accessible tree.
  const inTree = await note.evaluate((el) =>
    el.getAttribute("aria-hidden") !== "true" && getComputedStyle(el).display !== "none");
  say(inTree, "the note is in the accessible tree (no aria-hidden, not display:none)");

  // ── 2 · THE GRID ROW ─────────────────────────────────────────────────────
  const boxOf = async (id) => page.locator(`#${id}`).boundingBox();
  const kind = await boxOf("applicant_kind");
  const channel = await boxOf("channel");
  const fullName = await boxOf("applicant_name");
  say(kind && channel && Math.abs(kind.y - channel.y) < 2 && channel.x > kind.x,
      "Applying as and Channel share ONE ROW",
      `kind y=${kind?.y} x=${kind?.x} · channel y=${channel?.y} x=${channel?.x}`);
  say(fullName && fullName.y > kind.y,
      "Full name has moved down to row two", `y=${fullName?.y}`);

  // ── 3 · THE RHYTHM (B14 rule 39 — field → field 20px) ────────────────────
  const gaps = await page.evaluate(() => {
    const stack = document.querySelector("[data-field-stack]");
    if (!stack) return { error: "no [data-field-stack] in the step 1 panel" };
    const cs = getComputedStyle(stack);
    const kids = [...stack.children].filter((k) => k.getBoundingClientRect().height > 0);
    const between = [];
    for (let i = 1; i < kids.length; i += 1) {
      const a = kids[i - 1].getBoundingClientRect();
      const b = kids[i].getBoundingClientRect();
      between.push(Math.round(b.top - a.bottom));
    }
    const grid = document.querySelector("#applicant_kind")?.closest("div.grid");
    return { rowGap: cs.rowGap, between, gridRowGap: grid ? getComputedStyle(grid).rowGap : null };
  });
  say(gaps.rowGap === "20px", "the step-1 panel stacks on a 20px rhythm (rule 39)",
      JSON.stringify(gaps));
  say(gaps.gridRowGap === "20px", "and the grid's own row gap is the same 20px");

  // ── 4 · THE BANNER ───────────────────────────────────────────────────────
  const bannerIsPanel = await page.evaluate(() => {
    const b = document.querySelector('[data-banner="capturing-for-a-customer"]');
    return b ? { text: b.innerText.trim(), isPanel: b.hasAttribute("data-panel") } : null;
  });
  say(bannerIsPanel && !bannerIsPanel.isPanel,
      "CAPTURING FOR A CUSTOMER is no longer a panel of its own",
      JSON.stringify(bannerIsPanel));

  // ── 5 · A DRAFT FROM THE NAME ALONE ──────────────────────────────────────
  await page.fill("#applicant_name", "Osei, Grace");
  say(await save.isEnabled(), "with a name typed, Save as draft goes LIVE on step 1");
  say((await note.count()) === 0, "…and the short message goes with it");
  await save.click();
  await page.waitForTimeout(3000);
  const footer = (await page.locator("body").innerText()).match(/SR-\d\d-\d+/);
  say(Boolean(footer), "the draft is created and NUMBERED from step 1",
      footer ? footer[0] : "(no number on screen)");
  const url1 = page.url();
  say(/[?&]request=/.test(url1), "the URL now carries the draft id", url1.split("?")[1] ?? "");

  // ── 6 · THE IMMUTABILITY WALK — reach step 3 the way a clerk does ───────
  // ⚠ **NOT BY RELOADING AT `?request=…&step=3`.** The wizard deliberately
  // never hydrates from the fetched draft — the file says so where the SSN is
  // built: "setForm is only ever called from update(), so the wizard never
  // hydrates from the fetched draft", and rehydrating it would erase a stored
  // SSN the read path cannot return. So resuming by URL lands on an EMPTY form
  // and `Save as draft` is correctly disabled. A clerk walks the steps.
  const requestId = new URL(url1).searchParams.get("request");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(1500);
  // Step 2 gates Continue on the customer category.
  await page.waitForSelector("#account_type_code", { timeout: 20000 });
  const firstCategory = await page.$eval("#account_type_code option:not([value=''])",
                                         (o) => o.value);
  await page.selectOption("#account_type_code", firstCategory);
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(1500);
  await page.waitForSelector("#address_as_given", { timeout: 20000 });
  say(!(await page.locator("#address_as_given").isDisabled()),
      "step 3 reached from step 1: the address field is WRITABLE on a draft "
      + "that was created without one (BR-CUS-070's trap is absent)");
  await page.fill("#address_as_given", "14 Willow Bend, Springfield");
  const save3 = page.getByRole("button", { name: "Save as draft" });
  say(await save3.isEnabled(), "Save as draft is live on step 3");
  await save3.click({ timeout: 20000 });
  await page.waitForTimeout(3500);

  // Read it back FROM THE SERVER, in this session, after a full page load.
  const stored = await page.evaluate(async (id) => {
    const r = await fetch(`/api/brazosbend/service-requests/${id}`, {
      headers: { Accept: "application/json" },
    });
    const j = await r.json();
    return { status: r.status, address: j?.header?.address_as_given, no: j?.header?.request_no,
             state: j?.header?.state };
  }, requestId);
  say(stored.address === "14 Willow Bend, Springfield",
      "…and the server has stored it — read back on the request itself",
      JSON.stringify(stored));

  // ── 7 · SUBMIT STILL REFUSES WITHOUT AN ADDRESS ─────────────────────────
  const refused = await page.evaluate(async () => {
    const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
    const made = await fetch("/api/brazosbend/service-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({ channel: "physical_form", applicant_name: "Nkemdirim, Ada",
                             address_as_given: "" }),
    });
    const row = await made.json();
    const id = row?.header?.id ?? row?.id;
    const sub = await fetch(`/api/brazosbend/service-requests/${id}/submit`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: "{}",
    });
    return { created: made.status, no: row?.header?.request_no, id,
             submit: sub.status, body: await sub.text() };
  });
  say(refused.created === 201 || refused.created === 200,
      "a draft with a name and a BLANK address is created", `HTTP ${refused.created} ${refused.no}`);
  say([400, 422].includes(refused.submit) && refused.body.includes("address_as_given"),
      "…and SUBMIT refuses it, naming the address",
      `HTTP ${refused.submit} ${refused.body.slice(0, 160)}`);

  // ── 8 · REGRESSION WALK OF THE NEIGHBOURS — steps 2 to 6 ────────────────
  // The maintenance process asks for a regression walk of the neighbours, and
  // no gate here reads rendered output. Each step must draw a page-head title
  // and no raw catalogue key, on a draft that HAS no address — the state this
  // change made reachable for the first time.
  for (const n of [1, 2, 3, 4, 5, 6]) {
    await page.goto(`${BASE}/${TENANT}/requests/new?request=${refused.id}&step=${n}`,
                    { waitUntil: "networkidle" });
    await page.waitForSelector("h1", { timeout: 20000 });
    const h1 = (await page.locator("h1").first().innerText()).trim();
    const body = await page.locator("body").innerText();
    const key = body.match(/\b[a-z][A-Za-z0-9]*(\.[a-z][A-Za-z0-9]*){2,}\b/);
    const size = await page.locator("h1").first().evaluate((e) => getComputedStyle(e).fontSize);
    say(h1.length > 0 && !key,
        `step ${n} renders on an address-less draft`,
        `h1="${h1}" ${size} ${key ? "RAW KEY: " + key[0] : ""}`);
  }

} catch (e) {
  say(false, "walk threw", String(e).split("\n")[0]);
}

console.log(out.join("\n"));
console.log(errors.length ? `\nPAGE ERRORS / 5xx:\n${errors.join("\n")}` : "\nno page errors, no 5xx");
console.log(`\n${out.filter((l) => l.startsWith("PASS")).length}/${out.length} checks passed`);
await browser.close();
