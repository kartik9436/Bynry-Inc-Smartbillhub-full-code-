// ── Trace ──────────────────────────────────────────────
// Change:  `CR-142-BRC07` `P4.6` (the Reports settings section) and `P5.12`
//          (the door to it), walked in a real browser at 1440 and 1280.
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          CLAUDE.md hard-won law 6 (no gate in this repo looks at rendered
//          output) · law 7 clause 3 (a check's output must distinguish pass
//          from fail to a READER, not merely to an exit code).
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY RETENTION PROOF IS A PAIR.** A screenshot of a form with `3` in it
// proves a form RENDERS. What had to be proved is that the number DOES
// something, so the retention steps photograph screen `5·1`'s sentence BEFORE
// the change and AFTER it, and print both values.
//
// ⚠ **A STEP THIS FIXTURE CANNOT PERFORM IS ANNOUNCED AS `CANNOT` AND
// COUNTED**, never passed quietly — law 7's fifth shape, a check reporting zero
// over a scope it silently excludes.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8180";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const CLERK = process.env.CLERK ?? "";
const CLERK_PASSWORD = process.env.CLERK_PASSWORD ?? PASSWORD;
const OUT = process.env.OUT ?? "/tmp/p4-6-retention";
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
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH or install to /opt/pw-browsers");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...parts) => console.log(...parts);
let failures = 0;
let unprovable = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}
function cannot(label, why) {
  say(`CANNOT ${label} — ${why}`);
  unprovable += 1;
}

async function signIn(email, password, width) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return page;
}

const REF = `${BASE}/${TENANT}/settings/reference-data/reference-data`;

async function retentionSentence(page) {
  await page.goto(`${BASE}/${TENANT}/reports/history`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  return page.$eval("[data-retention-note]", (n) => n.textContent.trim()).catch(() => "");
}

for (const width of [1440, 1280]) {
  say(`\n══════════ ${width}px ══════════`);
  const page = await signIn(EMAIL, PASSWORD, width);
  say(`signed in as ${EMAIL} at ${BASE}`);

  // ═══════════════════════════════════════════════════════════════════════
  // 1 · THE SECTION EXISTS, WITH ITS TWO CARDS
  // ═══════════════════════════════════════════════════════════════════════
  await page.goto(REF, { waitUntil: "networkidle" });
  // ⚠ **WAIT FOR THE GRID, DO NOT SLEEP AND HOPE.** The first run of this
  // script slept 1500ms and reported the two cards MISSING at 1280 over a page
  // that draws them perfectly — the second sign-in was simply slower. A fixed
  // sleep is a check whose answer depends on the machine's mood, which is law
  // 7's *looking at the wrong thing* with a stopwatch.
  await page
    .waitForFunction(
      () => [...document.querySelectorAll(".lookup-group-heading")].some((n) => /reports/i.test(n.textContent ?? "")),
      { timeout: 20000 },
    )
    .catch(() => undefined);
  const bodyText = await page.$eval("body", (n) => n.innerText);
  check(`${width} · a REPORTS heading is on the grid`, /REPORTS/i.test(bodyText));
  check(`${width} · the File retention card is drawn`, /File retention/i.test(bodyText));
  check(`${width} · the Default format card is drawn`, /Default format/i.test(bodyText));
  check(
    `${width} · P5.5's two cards are NOT drawn (not built, and not promised)`,
    !/Report groups/i.test(bodyText) && !/Where a scheduled report goes/i.test(bodyText),
  );
  await page.screenshot({ path: `${OUT}/${width}-01-reference-grid.png`, fullPage: true });
  // ⚠ The grid scrolls an INNER container, so `fullPage` stops at the viewport
  // and a screenshot of the top proves nothing about a section at the bottom.
  await page.evaluate(() => {
    const heading = [...document.querySelectorAll(".lookup-group-heading")].find((n) =>
      /reports/i.test(n.textContent ?? ""),
    );
    if (heading) heading.scrollIntoView({ block: "center" });
  });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/${width}-00-reports-section.png` });

  // ═══════════════════════════════════════════════════════════════════════
  // 2 · THE RETENTION SENTENCE — **BEFORE**
  // ═══════════════════════════════════════════════════════════════════════
  const before = await retentionSentence(page);
  say(`   BEFORE · 5·1 retention line reads: ${JSON.stringify(before)}`);
  check(`${width} · the line is on screen 5·1`, before !== "");
  const door = await page.$("[data-retention-door]");
  check(`${width} · P5.12 · an admin is given a door`, door !== null);
  const href = door === null ? "" : await door.getAttribute("href");
  say(`   door href: ${JSON.stringify(href)}`);
  check(
    `${width} · …and it opens the File retention card itself, not the grid's top`,
    (href ?? "").includes("?list=file_retention"),
    href ?? "",
  );
  await page.screenshot({ path: `${OUT}/${width}-02-history-before.png`, fullPage: true });

  // ═══════════════════════════════════════════════════════════════════════
  // 3 · WALK THROUGH THE DOOR AND CHANGE THE VALUE
  // ═══════════════════════════════════════════════════════════════════════
  if (door !== null) {
    await door.click();
    await page.waitForTimeout(1800);
    const formText = await page.$eval("body", (n) => n.innerText);
    check(
      `${width} · the door lands ON the File retention form`,
      /File retention/i.test(formText) && /Keep downloads for/i.test(formText),
    );
    await page.screenshot({ path: `${OUT}/${width}-03-retention-form.png`, fullPage: true });

    // ⚠ **THE FIELD IS A TEXT INPUT, NOT `type=number`** — every rule-page
    // value is held and sent as TEXT (CLAUDE.md rule 2, so a decimal is never
    // parsed into a binary float). The first draft of this walkthrough looked
    // for `input[type=number]`, found nothing, and reported CANNOT over a form
    // that works perfectly. The id is the parameter's own key.
    const input = await page.$("#file_retention_days");
    if (input === null) {
      cannot(`${width} · change the value`, "no numeric input found on the form");
    } else {
      const was = await input.inputValue();
      const wanted = was.trim() === "9" ? "5" : "9";
      await input.fill(wanted);
      const save = await page.$('button:has-text("Save")');
      if (save === null) {
        cannot(`${width} · save`, "no Save button on the form");
      } else {
        await save.click();
        await page.waitForTimeout(2000);
        await page.screenshot({ path: `${OUT}/${width}-04-saved.png`, fullPage: true });
        // Re-open from a cold load — a value that survives a reload is stored.
        await page.goto(`${REF}?list=file_retention`, { waitUntil: "networkidle" });
        await page.waitForTimeout(1500);
        const reread = await page.$eval("#file_retention_days", (n) => n.value).catch(() => "");
        check(`${width} · the value PERSISTED across a reload`, reread === wanted, `was ${was} → ${reread}`);
        await page.screenshot({ path: `${OUT}/${width}-05-persisted.png`, fullPage: true });

        // ═══════════════════════════════════════════════════════════════
        // 4 · THE SENTENCE — **AFTER**. This is the pair that matters.
        // ═══════════════════════════════════════════════════════════════
        const after = await retentionSentence(page);
        say(`   AFTER  · 5·1 retention line reads: ${JSON.stringify(after)}`);
        check(
          `${width} · the setting REACHED the screen it governs`,
          after !== before && after.includes(wanted),
          `${JSON.stringify(before)} → ${JSON.stringify(after)}`,
        );
        await page.screenshot({ path: `${OUT}/${width}-06-history-after.png`, fullPage: true });

        // Put it back, so the next width starts where this one did.
        await page.goto(`${REF}?list=file_retention`, { waitUntil: "networkidle" });
        await page.waitForTimeout(1200);
        const back = await page.$("#file_retention_days");
        if (back !== null) {
          await back.fill(was);
          const saveAgain = await page.$('button:has-text("Save")');
          if (saveAgain !== null) {
            await saveAgain.click();
            await page.waitForTimeout(1500);
          }
        }
      }
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // 5 · THE DEFAULT FORMAT CARD
  // ═══════════════════════════════════════════════════════════════════════
  await page.goto(`${REF}?list=default_format`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const fmt = await page.$eval("body", (n) => n.innerText);
  check(`${width} · the Default format form opens`, /Default format/i.test(fmt));
  // ⚠ **READ THE INPUT'S VALUE, NOT `innerText`.** `innerText` does not contain
  // what is INSIDE an input, so the first draft of this check reported FAIL
  // over a control that reads `CSV` in the screenshot beside it. That is law
  // 7's *looking at the wrong thing*, caught by comparing the check against the
  // picture it was taken with.
  const fmtValue = await page.$eval("#default_download_format", (n) => n.value).catch(() => "");
  check(`${width} · …and the control reads CSV`, fmtValue === "CSV", JSON.stringify(fmtValue));
  const fmtReadOnly = await page
    .$eval("#default_download_format", (n) => n.readOnly || n.disabled)
    .catch(() => null);
  check(`${width} · …fixed, because one value is ratified`, fmtReadOnly === true, String(fmtReadOnly));
  await page.screenshot({ path: `${OUT}/${width}-07-default-format.png`, fullPage: true });

  await page.close();
}

// ═══════════════════════════════════════════════════════════════════════════
// 6 · A CLERK SEES THE FACT AND NO LINK
// ═══════════════════════════════════════════════════════════════════════════
if (CLERK === "") {
  cannot(
    "6 · the clerk half in a browser",
    "no CLERK= address was given. The seeded billing clerk (sam.reyes@sample.test) is " +
      "status=invited with no usable password — a FIXTURE gap, not a product one. " +
      "The assertion is made in retentionDoor.dom.test.tsx instead, which mounts the " +
      "component under the real route pattern with a billing_clerk permissions payload.",
  );
} else {
  const clerk = await signIn(CLERK, CLERK_PASSWORD, 1440);
  const sentence = await retentionSentence(clerk);
  check("6 · a clerk STILL sees the fact", sentence !== "", sentence);
  const clerkDoor = await clerk.$("[data-retention-door]");
  check("6 · …and is given no door", clerkDoor === null);
  await clerk.screenshot({ path: `${OUT}/1440-08-clerk-history.png`, fullPage: true });
  await clerk.close();
}

await browser.close();
say(`\n${failures} FAIL · ${unprovable} CANNOT · screenshots in ${OUT}`);
process.exit(failures === 0 ? 0 : 1);
