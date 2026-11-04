#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-144-BRC07 (FB10) — three builds, three API hosts. This is the
//          check that the bundle on disk actually calls THIS environment's API
//          and no other environment's.
// Rules:   CLAUDE.md hard-won law 7 (prove a guard RED first, in the harness
//          that will run it; and ask what would make it pass WRONGLY) · law 3
//          (defaults fail closed).
// ───────────────────────────────────────────────────────
//
//   node scripts/checkBundleHost.mjs <mode> [dist-dir]
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS EXISTS TO CATCH, AND WHY NOTHING ELSE CAN
// ══════════════════════════════════════════════════════════════════════════
// The API origin is INLINED into the JavaScript at build time. So a production
// deploy built with the sandbox env file is not a configuration mistake you can
// see anywhere — it is a bundle, byte-identical in shape, that quietly sends
// every production customer's data to the sandbox API. `tsc` cannot see it,
// no unit test can see it (they never build), and the running page looks
// perfect until somebody reads a network tab.
//
// So this reads the BUILT FILES, which is the only layer the fault exists in.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WOULD MAKE IT PASS WRONGLY — asked, per law 7 habit (2)
// ══════════════════════════════════════════════════════════════════════════
//  · *an empty dist* — refused: it counts the files it read and fails at zero,
//    because "no other host found" over nothing is law 7's report-zero shape.
//  · *the host appearing only in a comment or a source map* — `.map` files are
//    excluded and `.js`/`.html` are the only things read.
//  · *a substring collision* — `https://api-smart360.bynry.com` is a SUFFIX of
//    nothing, but `api-smart360-dev` CONTAINS `api-smart360`, so the foreign
//    scan matches a full origin followed by a non-host character. Without that,
//    a dev bundle would report the production host present. It is the bug this
//    check is most likely to have, so it has its own case.
//  · *the expected host missing while a foreign one is absent too* — both
//    halves are asserted, not just one.

import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { EXPECTED_API_ORIGIN } from "./deployConfig.mjs";

/** Files a built origin can legitimately appear in. `.map` is excluded on purpose. */
const READ_EXTENSIONS = [".js", ".html", ".css"];

async function filesUnder(dir) {
  const found = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...(await filesUnder(full)));
    } else if (READ_EXTENSIONS.some((ext) => entry.name.endsWith(ext))) {
      found.push(full);
    }
  }
  return found;
}

/**
 * True when `origin` appears as a WHOLE origin — not as the prefix of a longer
 * one. `https://api-smart360.bynry.com` must not match inside
 * `https://api-smart360-dev.bynry.com`.
 */
export function containsOrigin(text, origin) {
  let at = text.indexOf(origin);
  while (at !== -1) {
    const next = text[at + origin.length];
    if (next === undefined || !/[A-Za-z0-9.-]/.test(next)) {
      return true;
    }
    at = text.indexOf(origin, at + 1);
  }
  return false;
}

export async function checkBundleHost(mode, distDir) {
  const expected = EXPECTED_API_ORIGIN[mode];
  if (expected === undefined) {
    throw new Error(
      `unknown mode "${mode}" — expected one of ${Object.keys(EXPECTED_API_ORIGIN).join(", ")}`,
    );
  }
  const files = await filesUnder(distDir);
  if (files.length === 0) {
    // law 7: a check reporting zero over a scope it cannot see is the hardest
    // fault to spot, so an empty scope is a FAILURE and never a pass.
    throw new Error(`no ${READ_EXTENSIONS.join("/")} files under ${distDir} — nothing was checked`);
  }

  const foreign = Object.entries(EXPECTED_API_ORIGIN).filter(([name]) => name !== mode);
  const withExpected = [];
  const problems = [];

  for (const file of files) {
    const text = await readFile(file, "utf8");
    if (containsOrigin(text, expected)) {
      withExpected.push(file);
    }
    for (const [name, origin] of foreign) {
      if (containsOrigin(text, origin)) {
        problems.push(`${file} contains the ${name} API host ${origin}`);
      }
    }
  }

  if (withExpected.length === 0) {
    problems.push(
      `no file under ${distDir} contains this build's API host ${expected} ` +
        `(${files.length} files read) — the bundle would call its own static host`,
    );
  }

  return { expected, filesRead: files.length, withExpected, problems };
}

const invokedDirectly =
  process.argv[1] !== undefined &&
  fileURLToPath(import.meta.url) === fileURLToPath(new URL(`file://${process.argv[1]}`));

if (invokedDirectly) {
  const [, , mode, dist = "dist"] = process.argv;
  if (!mode) {
    console.error("usage: node scripts/checkBundleHost.mjs <mode> [dist-dir]");
    process.exit(2);
  }
  try {
    const result = await checkBundleHost(mode, dist);
    // law 7 habit (3): the OUTPUT distinguishes pass from fail to a reader, not
    // only to an exit code — and it prints the scope it covered.
    console.log(`mode         ${mode}`);
    console.log(`dist         ${dist}`);
    console.log(`files read   ${result.filesRead}`);
    console.log(`API host     ${result.expected}`);
    console.log(`found in     ${result.withExpected.length} file(s)`);
    if (result.problems.length > 0) {
      console.error(`\nFAIL — ${result.problems.length} problem(s):`);
      for (const one of result.problems) console.error(`  · ${one}`);
      process.exit(1);
    }
    console.log(`\nPASS — this bundle names the ${mode} API host and no other environment's.`);
  } catch (error) {
    console.error(`FAIL — ${error.message}`);
    process.exit(1);
  }
}
