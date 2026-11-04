#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 §2 row 10 — the POST-DEPLOY check that a bundle sends
//          to ITS OWN environment's PostHog project and to no other.
// Rules:   CLAUDE.md hard-won law 7 (prove a guard red first; ask what would
//          make it pass wrongly) · law 3 (fail closed).
// Tests:   src/analytics/checkAnalytics.test.ts (drives `inspectBundle`)
// ───────────────────────────────────────────────────────
//
//   VITE_POSTHOG_PROD_KEY_FINGERPRINT=<16 hex> \
//     node scripts/checkAnalytics.mjs <mode> --dist dist          # before upload
//   VITE_POSTHOG_PROD_KEY_FINGERPRINT=<16 hex> \
//     node scripts/checkAnalytics.mjs <mode> --url https://app.bynry.com   # after deploy
//
// `<mode>` is `dev`, `sandbox` or `production`. Exit 0 = pass, 1 = fail; every
// line printed says which check it is and what it found.
//
// WHAT IT CHECKS, ON THE BUILT FILES OR THE LIVE PAGE:
//   1. the page policy in `index.html` lets `connect-src` reach
//      `https://us.i.posthog.com` and `https://us-assets.i.posthog.com`, and
//      `script-src` is still `'self'` alone;
//   2. every PostHog project key (`phc_…`) in the JavaScript, by fingerprint:
//      a PRODUCTION bundle carries exactly one key and it IS the production
//      key; a DEV or SANDBOX bundle carries no production key at all;
//   3. the bundle carries an expected web host when it carries a key.
//
// WHAT WOULD MAKE IT PASS WRONGLY — asked, per law 7 habit (2):
//   · *no JavaScript read at all* — it counts the scripts it read and fails at
//     zero, because "no production key found" over nothing is law 7's
//     report-zero shape;
//   · *a key-less bundle* — that is a PASS for "off", and it is PRINTED as
//     "analytics OFF (no key in the bundle)", never as "keys correct", so a
//     deploy that was meant to carry a key and does not is visible;
//   · *the fingerprint missing* — refused: without it nothing can be compared.

import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const INGEST = "https://us.i.posthog.com";
const ASSETS = "https://us-assets.i.posthog.com";
const KEY = /\bphc_[A-Za-z0-9]{20,}\b/g;

export function fingerprint(key) {
  return createHash("sha256").update(key, "utf8").digest("hex").slice(0, 16);
}

/** Pure: the verdict over one page's HTML and its scripts. */
export function inspectBundle({ mode, html, scripts, prodFingerprint }) {
  const lines = [];
  let ok = true;
  const fail = (line) => {
    ok = false;
    lines.push(`FAIL  ${line}`);
  };
  const pass = (line) => lines.push(`ok    ${line}`);

  if (!/^[0-9a-f]{16}$/.test(prodFingerprint ?? "")) {
    fail("VITE_POSTHOG_PROD_KEY_FINGERPRINT is missing or not 16 hex characters — nothing can be compared");
    return { ok, lines };
  }
  if (scripts.length === 0) {
    fail("read 0 JavaScript files — a check over nothing is not a pass");
    return { ok, lines };
  }

  const meta = html.match(/<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]*)"/i);
  if (!meta) {
    fail("index.html carries no Content-Security-Policy meta tag");
  } else {
    const clauses = meta[1].split(";").map((one) => one.trim());
    const connect = clauses.find((one) => one.startsWith("connect-src ")) ?? "";
    const script = clauses.find((one) => one.startsWith("script-src ")) ?? "";
    connect.includes(INGEST) && connect.includes(ASSETS)
      ? pass("page policy: connect-src reaches PostHog US (ingest + assets)")
      : fail(`page policy: connect-src does not name ${INGEST} and ${ASSETS}: "${connect}"`);
    script === "script-src 'self'"
      ? pass("page policy: script-src is 'self' only")
      : fail(`page policy: script-src changed: "${script}"`);
  }

  const keys = new Set();
  for (const source of scripts) {
    for (const match of source.matchAll(KEY)) {
      keys.add(match[0]);
    }
  }
  const prints = [...keys].map(fingerprint);
  const carriesProd = prints.includes(prodFingerprint);
  pass(`read ${scripts.length} script(s); ${keys.size} PostHog key(s) found`);

  if (keys.size === 0) {
    lines.push("note  analytics OFF (no key in the bundle) — expected only for a build with no key");
    return { ok, lines };
  }
  if (keys.size > 1) {
    fail(`more than one PostHog key in one bundle (${keys.size})`);
  }
  if (mode === "production") {
    carriesProd
      ? pass("production bundle carries the PRODUCTION key")
      : fail("production bundle does NOT carry the production key");
  } else {
    carriesProd
      ? fail(`${mode} bundle carries the PRODUCTION key — it would send ${mode} data to production`)
      : pass(`${mode} bundle carries no production key`);
  }
  return { ok, lines };
}

async function fromDist(dir) {
  const html = await readFile(join(dir, "index.html"), "utf8");
  const assets = join(dir, "assets");
  const names = (await readdir(assets)).filter((name) => name.endsWith(".js"));
  const scripts = await Promise.all(names.map((name) => readFile(join(assets, name), "utf8")));
  return { html, scripts };
}

async function fromUrl(base) {
  const html = await (await fetch(base)).text();
  const first = [...html.matchAll(/<script[^>]+src="([^"]+\.js)"/g)].map((match) => new URL(match[1], base).href);
  // The entry script names its lazy chunks (posthog-js is one); follow them.
  const seen = new Set();
  const scripts = [];
  const queue = [...first];
  while (queue.length > 0 && seen.size < 400) {
    const href = queue.shift();
    if (seen.has(href)) continue;
    seen.add(href);
    const source = await (await fetch(href)).text();
    scripts.push(source);
    for (const match of source.matchAll(/["'`](?:\.\/|\/assets\/|assets\/)([A-Za-z0-9_.-]+\.js)["'`]/g)) {
      queue.push(new URL(`/assets/${match[1]}`, base).href);
    }
  }
  return { html, scripts };
}

async function main(argv) {
  const [mode, flag, where] = argv;
  if (!["dev", "sandbox", "production"].includes(mode) || !["--dist", "--url"].includes(flag) || !where) {
    console.error("usage: node scripts/checkAnalytics.mjs <dev|sandbox|production> --dist <dir> | --url <origin>");
    return 2;
  }
  const { html, scripts } = flag === "--dist" ? await fromDist(where) : await fromUrl(where);
  const verdict = inspectBundle({
    mode,
    html,
    scripts,
    prodFingerprint: (process.env.VITE_POSTHOG_PROD_KEY_FINGERPRINT ?? "").trim().toLowerCase(),
  });
  for (const line of verdict.lines) console.log(line);
  console.log(verdict.ok ? "PASS" : "FAIL");
  return verdict.ok ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then(
    (code) => process.exit(code),
    (error) => {
      console.error(`FAIL  ${error.message}`);
      process.exit(1);
    },
  );
}
