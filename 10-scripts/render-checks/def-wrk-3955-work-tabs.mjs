/**
 * RENDERED-OUTPUT CHECK — the Work module's tab strip IS the product's tab
 * strip, measured against Payments' in the same browser, on the same run.
 *
 * ⚠ **WHY THIS EXISTS, AND WHY NOTHING ELSE COULD HAVE FOUND IT.**
 * The Product Owner put Work and Payments side by side on 2026-09-05 and said,
 * verbatim: *"work - tabs does not match with our UI rules - ensure you follow
 * all UI rules for Work UI/screen while Ui is build as per images you ahev
 * taken"*. Payments' tabs were underlined; Work's were BOXED — a folder tab with
 * a border on three sides and the page colour behind it.
 *
 * **Nothing was broken.** Work's strip rendered, linked, marked its active tab,
 * carried an `aria-label`, named no internal id and passed `tsc`, eslint, every
 * gate and every unit test. It was a SECOND ANSWER to a question
 * `components/PageHeader.tsx` already answered for eight other features. B14
 * rule 36 is the rule (*"compose the kit"*), and `DEF-CWP-3655` is the same
 * shape one module along, where the portal grew a second kit that had to be
 * folded back.
 *
 * **No check in this repository reads rendered output** (CLAUDE.md hard-won law
 * 6), so a screen that looks unlike the rest of the product is invisible to all
 * of them — and the cost lands on a person noticing. The unit suite now refuses
 * a Work screen that draws its own strip, but it can only see MARKUP. It cannot
 * see that two strips built from the same component render the same pixels,
 * because a stylesheet rule that reaches a `<button>` and not an `<a>` is a
 * class of failure that has no DOM signature at all: `.page-header-tabs button`
 * would style Payments' buttons and leave Work's routed links unstyled, and
 * every assertion in the repo would still pass.
 *
 * **So this compares computed style, property by property, between two modules.**
 * That is the assertion the defect would have failed and nothing else can make.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   su postgres -c "psql -c 'create database sbh_workui owner smartbillhub'"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     DATABASE_URL="postgres://smartbillhub:<pw>@127.0.0.1:5432/sbh_workui"
 *   (cd 06-backend && python manage.py migrate --no-input && python manage.py seed_demo \
 *      && python manage.py load_sample_data --tenant brazosbend)
 *   (cd 06-backend && ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8115 --noreload &)
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4316 API_PROXY_TARGET=http://127.0.0.1:8115 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4316 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/def-wrk-3955-work-tabs.mjs
 *
 * ⚠ **BUILD THE BUNDLE.** A stale `dist/` is the most expensive way to read this
 * script's output, because every assertion passes or fails about a build nobody
 * is shipping.
 *
 * ── WHAT IT ASSERTS ───────────────────────────────────────────────────────
 *   1  **ONE STRIP PER WORK SCREEN, AND IT IS THE KIT'S.** `[data-page-header-tabs]`
 *      is present exactly once; the module's own `[data-work-tabs]` is gone by
 *      name on all four screens.
 *   2  **THE STRIP SITS BELOW THE TITLE**, which is where `BR-SHL-044` puts it
 *      and where Payments has always had it. Work drew it ABOVE the page head.
 *   3  **EVERY MEASURED PROPERTY MATCHES PAYMENTS** — the strip's layout and rule,
 *      and both tab states: colour, weight, size, the 2px underline, background,
 *      padding, text-decoration and the three borders that make a box a box.
 *   4  **THE ACTIVE TAB IS UNDERLINED, NOT BOXED** — stated as its own assertion
 *      rather than left implicit in (3), because it is the thing that was wrong.
 *   5  **A TAB IS STILL A LINK.** Composing the kit cost no behaviour: every Work
 *      tab is an `<a href>` a person can ⌘-click, which the boxed strip also was.
 *   6  **RULE 18's 80% CAP REACHES THE ONE SENTENCE.** It rode in the roll-up,
 *      which sets no width; it is the tab's explainer now, which sets
 *      `max-width: var(--desc-measure)`.
 *   7  **NO RAW TRANSLATION KEY IN ANY PROMPT** (`DEF-WRK-3957`) — the templates
 *      search box read the literal `work.templates.search`.
 *   8  **NO SIDEWAYS SCROLL AT 1440.**
 *   Screenshots land in `$SMOKE_OUT` beside `payments.png`, which is the point:
 *   a reviewer holds the two up together the way the PO did.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

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
          // try the next layout
        }
      }
    }
    throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4316";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/def-wrk-3955-work-tabs";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** The Work screens, and the one sentence each is supposed to cap at 80%. */
const WORK_SCREENS = [
  ["orders", "/work", "Everything open, across every connection and every account."],
  ["approvals", "/work/awaiting-approval", "The field has finished these. Nobody has accepted them yet."],
  ["parts", "/work/parts", "What your crews fit, and what each one costs."],
  ["templates", "/work/templates", "The jobs each service needs, written down once."],
];

/**
 * Everything about a tab strip that a person can SEE.
 *
 * ⚠ The three non-bottom borders are read on purpose. A boxed folder tab is
 * exactly "a top border, a left border and a background"; an underlined tab is
 * exactly "a bottom border and nothing else". Reading only the bottom border
 * would have passed on the defect.
 */
const READ_STRIP = () => {
  // The kit's strip if there is one; otherwise whatever the screen hand-rolled,
  // so the report can describe the defect instead of finding nothing.
  const strip =
    document.querySelector("[data-page-header-tabs]") ?? document.querySelector("[data-work-tabs]");
  if (strip === null) return null;
  const s = getComputedStyle(strip);
  const tab = (selected) =>
    [...strip.children].find((el) => el.getAttribute("aria-selected") === String(selected));
  const read = (el) => {
    if (el === undefined || el === null) return null;
    const c = getComputedStyle(el);
    return {
      tag: el.tagName,
      href: el.getAttribute("href"),
      color: c.color,
      fontWeight: c.fontWeight,
      fontSize: c.fontSize,
      background: c.backgroundColor,
      textDecoration: c.textDecorationLine,
      padding: `${c.paddingTop} ${c.paddingRight} ${c.paddingBottom} ${c.paddingLeft}`,
      borderBottom: `${c.borderBottomWidth} ${c.borderBottomStyle} ${c.borderBottomColor}`,
      borderTop: `${c.borderTopWidth} ${c.borderTopStyle}`,
      borderLeft: `${c.borderLeftWidth} ${c.borderLeftStyle}`,
      borderRight: `${c.borderRightWidth} ${c.borderRightStyle}`,
    };
  };
  const h1 = document.querySelector("h1");
  const explainer = document.querySelector(".page-header-explainer");
  return {
    strips: document.querySelectorAll("[data-page-header-tabs]").length,
    ownStrips: document.querySelectorAll("[data-work-tabs]").length,
    display: s.display,
    columnGap: s.columnGap,
    borderBottom: `${s.borderBottomWidth} ${s.borderBottomStyle} ${s.borderBottomColor}`,
    stripTop: Math.round(strip.getBoundingClientRect().top),
    titleTop: h1 === null ? null : Math.round(h1.getBoundingClientRect().top),
    active: read(tab(true)),
    resting: read(tab(false)),
    tabTags: [...strip.children].map((el) => el.tagName),
    tabHrefs: [...strip.children].map((el) => el.getAttribute("href")),
    explainer: explainer === null ? null : explainer.textContent.trim(),
    explainerWidth: explainer === null ? null : Math.round(explainer.getBoundingClientRect().width),
    // The column the description is measured against — the header's own box,
    // not the window, because the rail takes 240px of it.
    columnWidth:
      explainer === null ? null : Math.round(explainer.parentElement.getBoundingClientRect().width),
    prompts: [...document.querySelectorAll("input")].map((i) => i.placeholder).filter(Boolean),
  };
};

/** Which properties must match Payments exactly, and under which state. */
const SHARED = [
  "display",
  "columnGap",
  "borderBottom",
];
const PER_TAB = [
  "color",
  "fontWeight",
  "fontSize",
  "background",
  "textDecoration",
  "padding",
  "borderBottom",
  "borderTop",
  "borderLeft",
  "borderRight",
];

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });

  console.log(`def-wrk-3955: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page);

  // ═════════════════════════════════════════════════════════════════════════
  // The reference: Payments, the screen the PO held Work up against.
  // ═════════════════════════════════════════════════════════════════════════
  await page.goto(`${BASE}/${TENANT}/payments`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-page-header-tabs]", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "payments.png"), fullPage: true });
  const reference = await page.evaluate(READ_STRIP);
  if (reference === null) {
    console.log("⛔ Payments drew no tab strip — the reference is gone, not Work");
    process.exit(1);
  }
  console.log(
    `\n── reference · Payments: ${reference.active.tag} active ${reference.active.color}, ` +
      `underline ${reference.active.borderBottom}`,
  );

  for (const [name, path, sentence] of WORK_SCREENS) {
    console.log(`\n── Work · ${name} (${path}) ──`);
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
    // ⚠ **WAIT FOR *A* STRIP, NOT FOR THE RIGHT ONE.** Waiting on
    // `[data-page-header-tabs]` alone made this script die with
    // *"Timeout … waiting for locator"* on the very defect it was written for —
    // a true failure that named nothing, which is the shape this repo has
    // already paid for twice (`DEF-174`, `DEF-182`: a check whose output cannot
    // tell pass from fail is worse than no check, because it is trusted). So it
    // settles on whatever strip the screen drew, and the assertions below say
    // WHICH one it was.
    await page
      .waitForSelector("[data-page-header-tabs], [data-work-tabs]", { timeout: 20000 })
      .catch(() => undefined);
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(OUT, `work-${name}.png`), fullPage: true });
    const seen = await page.evaluate(READ_STRIP);
    if (seen === null) {
      check(false, `${name} drew NO tab strip at all — the screen has no strip to compare`);
      continue;
    }

    // 1 · one strip, and it is the kit's
    check(seen.strips === 1, `exactly one shared strip on the screen (${seen.strips})`);
    check(seen.ownStrips === 0, `the module draws no strip of its own (${seen.ownStrips})`);

    // 2 · below the title, where BR-SHL-044 puts it
    check(
      seen.titleTop !== null && seen.stripTop > seen.titleTop,
      `the strip sits BELOW the title (title ${seen.titleTop}px, strip ${seen.stripTop}px)`,
    );

    // 3 · every measured property matches Payments
    for (const prop of SHARED) {
      check(
        seen[prop] === reference[prop],
        `strip ${prop} matches Payments (${seen[prop]})`,
      );
    }
    for (const state of ["active", "resting"]) {
      for (const prop of PER_TAB) {
        check(
          seen[state] !== null && seen[state][prop] === reference[state][prop],
          `${state} tab ${prop} matches Payments (${seen[state] === null ? "NO SUCH TAB" : seen[state][prop]})`,
        );
      }
    }

    // 4 · underlined, not boxed — the thing that was actually wrong
    const box = seen.active ?? { borderTop: "?", borderLeft: "?", borderRight: "?", borderBottom: "?", background: "?" };
    check(
      box.borderTop.startsWith("0px") &&
        box.borderLeft.startsWith("0px") &&
        box.borderRight.startsWith("0px"),
      `the active tab has NO box around it (top ${box.borderTop}, left ${box.borderLeft}, right ${box.borderRight})`,
    );
    check(
      !box.borderBottom.startsWith("0px") && box.borderBottom.includes("solid"),
      `the active tab is UNDERLINED (${box.borderBottom})`,
    );
    check(
      box.background === "rgba(0, 0, 0, 0)",
      `the active tab has no fill behind it (${box.background})`,
    );

    // 5 · a tab is still a link
    check(
      seen.tabTags.every((tag) => tag === "A"),
      `every Work tab is a real link (${[...new Set(seen.tabTags)].join(", ")})`,
    );
    check(
      seen.tabHrefs.every((href) => typeof href === "string" && href.startsWith(`/${TENANT}/work/`)),
      `every tab addresses a tenant-relative Work route`,
    );

    // 6 · rule 18's 80% cap reaches the one sentence
    check(
      seen.explainer !== null && seen.explainer.startsWith(sentence.slice(0, 40)),
      `the one sentence is the tab's explainer ("${(seen.explainer ?? "—").slice(0, 46)}…")`,
    );
    if (seen.explainerWidth !== null && seen.columnWidth) {
      const pct = Math.round((seen.explainerWidth / seen.columnWidth) * 100);
      check(pct <= 81, `the description caps at 80% of the column (measured ${pct}%)`);
    }

    // 7 · no raw translation key in a prompt (DEF-WRK-3957)
    const raw = seen.prompts.filter((p) => /^[a-z][a-zA-Z0-9_]*(\.[a-zA-Z0-9_]+)+$/.test(p));
    check(raw.length === 0, `no prompt reads its own key${raw.length ? ` — found ${raw.join(", ")}` : ""}`);

    // 8 · no sideways scroll
    const sideways = await page.evaluate(
      () => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
    );
    check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);
  }

  await browser.close();
  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n${failures.length} FAILED:`);
    for (const f of failures) console.log(`   ⛔ ${f}`);
    process.exit(1);
  }
  console.log("\nall checks passed — Work's tab strip is the product's tab strip");
})();
