#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — renders the pass/fail tables of the custom-fields
//          end-to-end walk (`cf_e2e_walk.mjs`) from its `results.json`, so the
//          walk report's tables are the walk's own output, never retyped.
//
//   node 10-scripts/cf_e2e_walk_report.mjs <results.json> > tables.md
// ───────────────────────────────────────────────────────
import { readFileSync } from "node:fs";

const results = JSON.parse(readFileSync(process.argv[2], "utf8"));
const m = results.matrix;
const cellText = (v) => (v === true ? "PASS" : v === false ? "**FAIL**" : "—");
function table(name, rows, cols, rowLabel = "Record type") {
  const t = m[name] ?? {};
  const out = [`| ${rowLabel} | ${cols.join(" | ")} |`, `|---|${cols.map(() => "---").join("|")}|`];
  for (const r of rows) out.push(`| ${r} | ${cols.map((c) => cellText(t[r]?.[c])).join(" | ")} |`);
  return out.join("\n");
}
const TYPES = ["accounts", "customers", "contacts", "addresses", "service_agreements", "premises", "units", "service_points",
  "assets", "work_orders", "meter_reads", "routes", "areas", "payments", "service_request", "portal"];
// the A table's isolation column is the AND of that record type's isolation row
for (const type of TYPES) {
  const iso = m.iso?.[type];
  if (iso) {
    const vals = Object.values(iso);
    (m.A ??= {})[type] = { ...(m.A[type] ?? {}), isolation: vals.length ? vals.every(Boolean) : undefined };
  }
}
const sections = [];
sections.push("### Utility A (Brazos Bend) — one field per record type\n");
sections.push(table("A", TYPES, ["set up", "typed", "shown", "imported", "off/on", "isolation"]));
sections.push("\n### Isolation (must pass) — utility B (Pine Hill) against A and SEU\n");
sections.push(table("iso", TYPES, ["screens", "API", "writes", "direct reads", "same-name", "DB", "settings rules"]));
sections.push("\n### Settings rules\n");
sections.push(table("rules", Object.keys(m.rules ?? {}), ["pass"], "Rule · utility"));
const seuRows = Object.keys(m.SEU ?? {});
sections.push("\n### SEU test (13 fields, PO's own definitions)\n");
sections.push(table("SEU", seuRows, ["set up", "route 1 · clerk", "New Connection step", "edit screen", "route 2 · portal", "Staff New Request", "copied on approval",
  "view · Account detail / Premise page", "view · Request detail"], "Field"));
sections.push("\n### Bills\n");
sections.push(table("bills", Object.keys(m.bills ?? {}), ["Settings", "stamp", "preview", "code"], "Rule"));
const checks = Object.entries(results.checks);
const failed = checks.filter(([, v]) => !v.ok);
sections.push(`\n**${checks.length} checks, ${checks.length - failed.length} passed, ${failed.length} failed.**\n`);
if (failed.length) {
  sections.push("| Failed check | Detail |\n|---|---|");
  for (const [k, v] of failed) sections.push(`| ${k.replace(/\|/g, "/")} | ${String(v.detail).replace(/\s+/g, " ").replace(/\|/g, "/").slice(0, 220)} |`);
}
process.stdout.write(sections.join("\n") + "\n");
