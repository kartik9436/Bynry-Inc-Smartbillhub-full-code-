// ── Trace ──────────────────────────────────────────────
// Ask:      Portal accessibility, Groups D and E — decision log 2026-10-23,
//           "Group D (language, titles, headings: F-05, F-07, F-20)" and
//           "Group E (names of controls and links: F-12, F-14, F-23, F-24)".
//           The tester's working rule: *"list every similar place before
//           changing anything"*.
// Results:  08-qa/a11y-portal-2026-10/group-d-inventory.md
// ───────────────────────────────────────────────────────
/**
 * portal_outline_scan — READ-ONLY. Visits every route in `portalRoutes.tsx`,
 * signed out and signed in, in each language asked for, and records:
 *
 *   * `<html lang>` and the i18n language AFTER the switch (WCAG 3.1.1);
 *   * every `lang` attribute below `<html>` and the language selector's
 *     options (3.1.2);
 *   * `document.title` (2.4.2);
 *   * the heading outline as the accessibility tree sees it — level, text,
 *     and whether it is visually hidden — with the h1 count and every skipped
 *     level (1.3.1, 2.4.6);
 *   * axe-core's select-name, link-name, button-name, label,
 *     aria-prohibited-attr, page-has-heading-one, heading-order,
 *     document-title, html-has-lang and valid-lang (Group E and D);
 *   * links that share an accessible name and go to DIFFERENT places (F-23),
 *     and where every "pay with a bill number" link points (F-24).
 *
 * It changes no product file.
 *
 * SET-UP (fake data only — the Pine Hill / Oak Ridge portal fixture):
 *     a private copy of a database seeded with `seed_portal_demo`;
 *     runserver on 127.0.0.1:<api>; `vite build` served by `server.mjs`.
 *     npm install --prefix <scratch> --no-save axe-core@4.10.3   # PINNED
 *     AXE_PATH=<scratch>/node_modules/axe-core/axe.min.js BASE=http://127.0.0.1:<fe> \
 *       PORTAL_LOGIN=alvarez0@example.invalid \
 *       node 10-scripts/a11y/portal_outline_scan.mjs --out=<dir> [--langs=en,es] [--auth=out,in]
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY (hard-won law 7):
 *   * a signed-in pass that is really signed out — the run REFUSES to go on
 *     when `/portal/session` does not answer 200 in the browser context;
 *   * a Spanish pass that is still English — the language is switched through
 *     the app's own i18n handle and BOTH `i18n.language` and `<html lang>` are
 *     read back per page, so a page that did not switch shows as `en`;
 *   * a page that never rendered — every page records its `data-screen` and
 *     its h1 count; a blank page shows `h1: 0`, never "clean";
 *   * a page whose heading list is read before the data arrives — the scan
 *     waits for the network to settle and then for the loading state to clear.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const FRONTEND = join(REPO, "07-frontend");
const SRC = join(FRONTEND, "src");
const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, v] = a.replace(/^--/, "").split("=");
    return [k, v ?? true];
  }),
);

const require = createRequire(join(FRONTEND, "package.json"));
const { chromium } = require("playwright");
const BASE = process.env.BASE ?? "http://127.0.0.1:4387";
const TENANT = process.env.PORTAL_TENANT ?? "pine-hill";
const LOGIN = process.env.PORTAL_LOGIN;
const PASSWORD = process.env.PORTAL_PASSWORD ?? "Sample-Portal-2026!";
const AXE = process.env.AXE_PATH;
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = resolve(String(args.out ?? "a11y-outline-out"));
const LANGS = String(args.langs ?? "en,es").split(",");
const AUTHS = String(args.auth ?? "out,in").split(",");
const AXE_RULES = [
  "select-name",
  "link-name",
  "button-name",
  "label",
  "aria-prohibited-attr",
  "page-has-heading-one",
  "heading-order",
  "document-title",
  "html-has-lang",
  "valid-lang",
];
if (!AXE || !existsSync(AXE)) throw new Error("AXE_PATH must name axe.min.js (axe-core@4.10.3)");
if (!args.from && AUTHS.includes("in") && !LOGIN) throw new Error("PORTAL_LOGIN is required for the signed-in pass");
mkdirSync(OUT, { recursive: true });

// ── every route the router mounts ──────────────────────────────────────────
const routes = [
  ...readFileSync(join(SRC, "portal/routing/portalRoutes.tsx"), "utf8").matchAll(
    /\{\s*path:\s*"([^"]*)",\s*element:\s*<(\w+)/g,
  ),
].map(([, path, element]) => ({ path, element }));
const register = [
  ...readFileSync(join(SRC, "portal/routing/screenIds.ts"), "utf8").matchAll(
    /\{\s*path:\s*"([^"]*)",\s*id:\s*"(CWP-\d+)"/g,
  ),
].map(([, path, id]) => ({ path, id }));
const idOf = (p) => register.find((r) => r.path === p)?.id ?? "(unregistered)";

// `--from=<dir>` re-reads a scan already taken (its outline.json) and only
// summarises and asserts it — so a BEFORE scan can be judged by the same rules
// as the AFTER one without loading 212 pages again.
let results;
if (args.from) {
  results = JSON.parse(readFileSync(join(resolve(String(args.from)), "outline.json"), "utf8"));
  if (args.utility) results.meta.params.utility = String(args.utility);
} else {
const LAUNCH = { ...(existsSync(CHROME) ? { executablePath: CHROME } : {}), args: ["--disable-dev-shm-usage", "--disable-gpu"] };
let browser = await chromium.launch(LAUNCH);
const rel = (p) => `/${TENANT}/portal` + (p === "/" ? "" : p);

// ── the references a :param needs, read through the API the screens read ──
const params = {};
{
  const ctx = await browser.newContext();
  const api = ctx.request;
  if (LOGIN) {
    const s = await api.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, {
      data: { email: LOGIN, password: PASSWORD },
    });
    if (!s.ok()) throw new Error(`sign-in refused: ${s.status()} ${(await s.text()).slice(0, 200)}`);
    const first = async (path, key, pick) => {
      const r = await api.get(`${BASE}/api/${TENANT}/portal${path}`);
      const b = r.ok() ? await r.json().catch(() => null) : null;
      const list = b?.[key] ?? b?.results;
      return Array.isArray(list) && list.length ? pick(list[0]) : null;
    };
    params.number = await first("/bills", "bills", (b) => b.number);
    params.reference = await first("/requests", "requests", (r) => r.reference ?? r.number);
  }
  const g = await api.get(`${BASE}/api/${TENANT}/portal/public/help`);
  params.helpSlug = g.ok() ? (await g.json())?.answers?.[0]?.slug : null;
  const c = await api.get(`${BASE}/api/${TENANT}/portal/public/service-centres`);
  params.centreSlug = c.ok() ? (await c.json())?.centres?.[0]?.slug : null;
  const f = await api.get(`${BASE}/api/${TENANT}/portal/public/front`);
  params.utility = f.ok() ? (await f.json())?.tenant?.name : null;
  await ctx.close();
}

const pages = [];
const skipped = [];
for (const r of routes) {
  let p = r.path;
  if (p.includes(":draft")) {
    skipped.push({ ...r, why: "a draft link is minted by the form, not typed" });
    continue;
  }
  if (p.includes(":number")) p = params.number ? p.replace(":number", params.number) : null;
  else if (p.includes(":reference")) p = params.reference ? p.replace(":reference", params.reference) : null;
  else if (p.includes(":slug"))
    p = p.startsWith("/help")
      ? params.helpSlug
        ? p.replace(":slug", params.helpSlug)
        : null
      : params.centreSlug
        ? p.replace(":slug", params.centreSlug)
        : null;
  if (!p) {
    skipped.push({ ...r, why: "no reference on this login" });
    continue;
  }
  pages.push({ route: r.path, path: p, id: idOf(r.path), element: r.element });
}

/** Runs in the page: what a screen reader would be given. */
const MEASURE = () => {
  const hidden = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === "none" || cs.visibility === "hidden" || n.getAttribute("aria-hidden") === "true" || n.hidden) return true;
    }
    return false;
  };
  const srOnly = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return (r.width <= 1 && r.height <= 1) || cs.clipPath === "inset(50%)" || cs.clip === "rect(0px, 0px, 0px, 0px)";
  };
  const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
  const name = (el) => {
    const by = el.getAttribute("aria-labelledby");
    if (by)
      return by
        .split(/\s+/)
        .map((id) => document.getElementById(id))
        .filter(Boolean)
        .map((n) => (n.getAttribute("aria-label") || text(n)))
        .join(" ")
        .trim();
    return (el.getAttribute("aria-label") || text(el)).trim();
  };
  const headings = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6,[role=heading]")]
    .filter((h) => !hidden(h))
    .map((h) => ({
      level: h.getAttribute("aria-level") ? Number(h.getAttribute("aria-level")) : Number(h.tagName.slice(1)) || 2,
      text: text(h).slice(0, 80),
      srOnly: srOnly(h),
      // The look, so a before/after can prove the size did not move.
      look: (() => {
        const cs = getComputedStyle(h);
        return `${cs.fontSize}/${cs.fontWeight}/${cs.marginBottom}/${cs.textTransform}`;
      })(),
    }));
  // A skip is a heading more than one level below the one before it. The page
  // starts as if under its h1, so a frame notice drawn ABOVE the h1 as an h2
  // is not a skip, and an h3 there is; `beforeH1` counts those separately.
  const skips = [];
  let prev = 1;
  for (const h of headings) {
    if (h.level > prev + 1) skips.push(`h${prev}→h${h.level} "${h.text}"`);
    prev = h.level;
  }
  const firstH1 = headings.findIndex((h) => h.level === 1);
  const beforeH1 = (firstH1 === -1 ? headings : headings.slice(0, firstH1)).map((h) => `h${h.level} "${h.text}"`);
  const links = [...document.querySelectorAll("a[href]")]
    .filter((a) => !hidden(a))
    .map((a) => ({ name: name(a), visible: text(a), href: a.getAttribute("href") }));
  const byName = {};
  for (const l of links) (byName[l.name] ??= new Set()).add(l.href.replace(/[?#].*$/, ""));
  const sharedNames = Object.entries(byName)
    .filter(([, set]) => set.size > 1)
    .map(([n, set]) => ({ name: n, destinations: [...set] }));
  const quickPay = links.filter((l) => /bill number|número de factura/i.test(l.visible)).map((l) => l.href);
  const langAttrs = [...document.querySelectorAll("body [lang]")].map((e) => `${e.tagName.toLowerCase()}[lang=${e.getAttribute("lang")}] ${text(e).slice(0, 30)}`);
  const langSelect = [...document.querySelectorAll("select[data-guest-language] option, select[data-language] option")].map(
    (o) => `${o.textContent}:${o.getAttribute("lang") ?? "-"}`,
  );
  const unnamed = [...document.querySelectorAll("select, input:not([type=hidden]), textarea, button")]
    .filter((e) => !hidden(e))
    .filter((e) => {
      if (e.getAttribute("aria-label") || e.getAttribute("aria-labelledby") || e.title) return false;
      if (e.tagName === "BUTTON") return !text(e);
      if (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) return false;
      if (e.closest("label")) return false;
      return true;
    })
    .map((e) => e.outerHTML.slice(0, 120));
  return {
    htmlLang: document.documentElement.lang,
    i18n: window.__SMARTBILLHUB_I18N__?.language ?? null,
    title: document.title,
    screen: document.querySelector("[data-screen]")?.getAttribute("data-screen") ?? null,
    loading: !!document.querySelector("[data-portal-state=loading], [aria-busy=true]"),
    headings,
    h1: headings.filter((h) => h.level === 1).length,
    h1Text: headings.filter((h) => h.level === 1).map((h) => h.text),
    skips,
    beforeH1,
    sharedNames,
    quickPay,
    langAttrs,
    langSelect,
    unnamed,
  };
};

results = { meta: { base: BASE, tenant: TENANT, langs: LANGS, auths: AUTHS, at: new Date().toISOString(), routes: routes.length, scanned: pages.length, skipped, params }, runs: [] };

for (const auth of AUTHS) {
  // A crashed renderer — or a crashed browser — is recorded and the run goes
  // on with a fresh tab, signed in again where the pass is signed in.
  let context;
  let page;
  const open = async () => {
    for (let tries = 1; ; tries++) {
      try {
        if (!browser.isConnected()) browser = await chromium.launch(LAUNCH);
        context = await browser.newContext({ viewport: { width: 1280, height: 900 }, bypassCSP: true });
        break;
      } catch (err) {
        if (tries >= 4) throw err;
        await browser.close().catch(() => {});
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
    page = await context.newPage();
    page.on("dialog", (d) => d.dismiss().catch(() => {}));
    if (auth === "in") {
      const s = await page.request.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, { data: { email: LOGIN, password: PASSWORD } });
      if (!s.ok()) throw new Error(`sign-in refused in browser context: ${s.status()}`);
      const me = await page.request.get(`${BASE}/api/${TENANT}/portal/session`);
      if (!me.ok()) throw new Error(`signed-in pass is not signed in: /portal/session answered ${me.status()}`);
    }
  };
  const fresh = async () => {
    await context?.close().catch(() => {});
    await open();
  };
  await open();
  for (const lang of LANGS) {
    for (const pg of pages) {
     for (let attempt = 1; attempt <= 3; attempt++) {
      try {
      await page.goto(BASE + rel(pg.path), { waitUntil: "load", timeout: 25000 }).catch(() => {});
      await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
      await page.waitForSelector("[data-screen], main", { timeout: 8000 }).catch(() => {});
      // the first load, BEFORE any switch — what <html lang> says on arrival
      const arrival = await page.evaluate(() => ({ htmlLang: document.documentElement.lang, i18n: window.__SMARTBILLHUB_I18N__?.language }));
      if (lang !== "en") {
        await page.evaluate(async (l) => {
          await window.__SMARTBILLHUB_I18N__?.changeLanguage(l);
        }, lang);
      } else {
        await page.evaluate(async () => {
          if (window.__SMARTBILLHUB_I18N__?.language !== "en") await window.__SMARTBILLHUB_I18N__?.changeLanguage("en");
        });
      }
      await page.waitForFunction(() => !document.querySelector("[data-portal-state=loading]"), null, { timeout: 6000 }).catch(() => {});
      await page.waitForTimeout(500);
      const m = await page.evaluate(MEASURE);
      if (!(await page.evaluate(() => typeof window.axe !== "undefined"))) await page.addScriptTag({ path: AXE });
      const axe = await page.evaluate(async (rules) => {
        const r = await window.axe.run(document, { runOnly: { type: "rule", values: rules }, resultTypes: ["violations"] });
        return r.violations.map((v) => ({ rule: v.id, count: v.nodes.length, nodes: v.nodes.slice(0, 6).map((n) => n.html.slice(0, 140)) }));
      }, AXE_RULES);
      results.runs.push({ auth, lang, ...pg, finalUrl: page.url().replace(BASE, ""), arrival, ...m, axe });
      process.stdout.write(`${auth} ${lang} ${pg.path.padEnd(34)} lang=${m.htmlLang} h1=${m.h1} skips=${m.skips.length} axe=${axe.map((a) => `${a.rule}:${a.count}`).join(",")} title="${m.title}"\n`);
      break;
      } catch (err) {
        process.stdout.write(`${auth} ${lang} ${pg.path} attempt ${attempt} FAILED: ${String(err).slice(0, 120)}\n`);
        await fresh();
        if (attempt === 3) results.runs.push({ auth, lang, ...pg, error: String(err).slice(0, 200), arrival: {}, headings: [], h1: -1, h1Text: [], skips: [], sharedNames: [], quickPay: [], axe: [], title: "(error)", htmlLang: "(error)" });
      }
     }
    }
  }
  // The UI path for the language switch, once: the guest selector itself.
  if (auth === "out") {
    await page.goto(BASE + rel("/"), { waitUntil: "networkidle" }).catch(() => {});
    await page.evaluate(async () => window.__SMARTBILLHUB_I18N__?.changeLanguage("en"));
    const sel = page.locator("select[data-guest-language]");
    if (await sel.count()) {
      await sel.selectOption("es");
      await page.waitForTimeout(400);
      results.meta.uiSwitch = await page.evaluate(() => ({ htmlLang: document.documentElement.lang, i18n: window.__SMARTBILLHUB_I18N__?.language }));
      await sel.selectOption("en").catch(() => {});
    } else results.meta.uiSwitch = "no guest language selector on the front page";
  }
  await context.close();
}
await browser.close();

}
writeFileSync(join(OUT, "outline.json"), JSON.stringify(results, null, 2));

// ── a summary a person can read ────────────────────────────────────────────
const lines = [];
const runs = results.runs;
const titles = new Set(runs.map((r) => r.title));
lines.push(`# Portal outline scan — ${results.meta.at}`, "");
lines.push(`Routes in portalRoutes.tsx: **${results.meta.routes}** · scanned: **${results.meta.scanned}** · skipped: **${results.meta.skipped.length}** (${results.meta.skipped.map((s) => `${s.path} — ${s.why}`).join("; ") || "none"})`);
lines.push(`Runs: **${runs.length}** (${AUTHS.join("/")} × ${LANGS.join("/")}). Distinct document titles: **${titles.size}**.`);
lines.push(`UI language switch on the front page: ${JSON.stringify(results.meta.uiSwitch)}`, "");
const wrongLang = runs.filter((r) => r.htmlLang !== r.lang);
lines.push(`html lang ≠ chosen language: **${wrongLang.length} of ${runs.length}** runs.`);
const noH1 = runs.filter((r) => r.h1 !== 1);
lines.push(`runs with h1 count ≠ 1: **${noH1.length}** · runs with a skipped level: **${runs.filter((r) => r.skips.length).length}**`);
const h1Map = {};
for (const r of runs.filter((r) => r.lang === "en" && r.h1 === 1)) (h1Map[r.h1Text[0]] ??= new Set()).add(`${r.auth}:${r.path}`);
const dupH1 = Object.entries(h1Map).filter(([, s]) => s.size > 1 && new Set([...s].map((x) => x.split(":")[1])).size > 1);
lines.push(`h1 text shared by different pages (en): **${dupH1.length}** ${dupH1.map(([t, s]) => `"${t}" (${[...s].join(", ")})`).join("; ")}`);
const axeTotals = {};
for (const r of runs) for (const a of r.axe) axeTotals[a.rule] = (axeTotals[a.rule] ?? 0) + a.count;
lines.push(`axe totals over all runs: ${Object.entries(axeTotals).map(([k, v]) => `${k} ${v}`).join(" · ") || "none"}`);
lines.push(`runs with links sharing a name across destinations: **${runs.filter((r) => r.sharedNames.length).length}**`);
const qp = new Set(runs.flatMap((r) => r.quickPay));
lines.push(`"bill number" quick-pay link destinations seen: ${[...qp].join(", ") || "none"}`, "");
lines.push("| auth | lang | path | screen | html lang (arrival → after) | title | h1 | skips | axe | shared link names |", "|---|---|---|---|---|---|---|---|---|---|");
for (const r of runs)
  lines.push(
    `| ${r.auth} | ${r.lang} | \`${r.path}\` | ${r.screen ?? "—"} | ${r.arrival.htmlLang} → ${r.htmlLang} | ${r.title} | ${r.h1}${r.h1Text.length ? ` (${r.h1Text.join(" / ")})` : ""} | ${r.skips.join("; ") || "—"} | ${r.axe.map((a) => `${a.rule} ${a.count}`).join(", ") || "—"} | ${r.sharedNames.map((s) => `"${s.name}"×${s.destinations.length}`).join("; ") || "—"} |`,
  );
writeFileSync(join(OUT, "outline.md"), lines.join("\n") + "\n");
console.log(`\nwrote ${join(OUT, "outline.md")} and outline.json`);

// ── --assert: the Group D and E rules as a pass/fail, for before/after ─────
// Every failure is named. What is NOT judged is counted and printed beside
// what is (law 7: a blind spot with no number is indistinguishable from an
// empty one).
if (args.assert) {
  const fails = [];
  const notJudged = { crashed: 0, failureCard: 0 };
  const E_RULES = ["select-name", "link-name", "button-name", "label", "aria-prohibited-attr"];
  for (const r of runs) {
    const where = `${r.auth} ${r.lang} ${r.path}`;
    if (r.error) {
      notJudged.crashed++;
      continue;
    }
    if (r.htmlLang !== r.lang) fails.push(`${where}: html lang ${r.htmlLang}`);
    if (r.h1 !== 1) fails.push(`${where}: ${r.h1} h1`);
    for (const s of r.skips) fails.push(`${where}: skip ${s}`);
    for (const b of r.beforeH1 ?? []) if (r.h1 === 1 && !/^h2 /.test(b)) fails.push(`${where}: above the h1 ${b}`);
    const want = r.h1 === 1 && results.meta.params.utility ? `${r.h1Text[0]} · ${results.meta.params.utility}` : null;
    if (want !== null && r.title !== want) fails.push(`${where}: title "${r.title}" (want "${want}")`);
    if (r.h1 !== 1 && /SMART360 Next/.test(r.title)) fails.push(`${where}: title "${r.title}"`);
    for (const s of r.sharedNames) fails.push(`${where}: "${s.name}" names ${s.destinations.length} places`);
    for (const q of r.quickPay) if (!/\/portal\/pay$/.test(q)) fails.push(`${where}: quick pay → ${q}`);
    for (const a of r.axe) if (E_RULES.includes(a.rule)) fails.push(`${where}: axe ${a.rule} ×${a.count}`);
  }
  // No two PAGES share an h1. The shared failure card (no data-screen) is a
  // state every signed-in address shows when signed out, not a page.
  const KNOWN = new Set(["CWP-004|CWP-077"]); // no-receipt refusal states — reported, not changed (decision log)
  for (const lang of LANGS) {
    const map = new Map();
    for (const r of runs.filter((r) => !r.error && r.lang === lang && r.h1 === 1)) {
      if (!r.screen) {
        notJudged.failureCard++;
        continue;
      }
      (map.get(r.h1Text[0]) ?? map.set(r.h1Text[0], new Set()).get(r.h1Text[0])).add(r.screen);
    }
    for (const [text, screens] of map) {
      if (screens.size < 2) continue;
      const key = [...screens].sort().join("|");
      if (KNOWN.has(key)) console.log(`  known, reported: "${text}" ← ${key}`);
      else fails.push(`${lang}: h1 "${text}" on ${key}`);
    }
  }
  console.log(`\nASSERT: ${runs.length} loads · ${fails.length} failure(s) · not judged: ${notJudged.crashed} crashed tab(s), ${notJudged.failureCard} failure-card load(s) left out of the shared-h1 check`);
  for (const f of fails.slice(0, 400)) console.log(`  FAIL ${f}`);
  writeFileSync(join(OUT, "assert.txt"), fails.join("\n") + "\n");
  process.exitCode = fails.length === 0 ? 0 : 1;
}
