/**
 * DEF-MET-5624 walked in a browser — a utility with no City sees no GIS
 * furniture, and one with a City still does.
 *
 * ⚠ **BOTH DIRECTIONS ON ONE STACK, BECAUSE ONE DIRECTION IS NOT A PROOF.**
 * Brazos Bend HAS a `gis_esri` connection, so it is the PRESENT half; the
 * ABSENT half is the same tenant with that connection switched off for the
 * length of the run and put back in a `finally`, printed both ways.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: the words *On the map* and *Checked
 * against GIS* also appear on the REVIEW step's row list, so matching text over
 * the page passes in both directions. Every assertion addresses
 * `[data-testid="found-on-the-city-map"]`, which exists for no other reason.
 */
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire("/tmp/claude-0/-home-user-SMARTBillHub/7a2c3288-d09c-5c49-9c79-5268de69b08a/scratchpad/lane2/07-frontend/package.json");
const { chromium } = require("playwright");
const BASE = "http://127.0.0.1:8082";
const T = "brazosbend";
const PGURL = "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_lane2?sslmode=disable";
const TENANT = "01a0aed7-0524-7f61-ba38-eac930fb2411";
const sql = (q) =>
  execFileSync("psql", [PGURL, "-tAc", `set app.tenant_id='${TENANT}'; ${q}`], { encoding: "utf8" })
    .split("\n").filter((l) => !["SET", "UPDATE 1"].includes(l.trim())).join("\n").trim();
function chrome() {
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean))
    if (existsSync(root)) for (const d of readdirSync(root)) {
      const c = join(root, d, "chrome-linux", "chrome"); if (existsSync(c)) return c;
    }
  throw new Error("no chromium");
}
let fails = 0;
const say = (l, ok, d = "") => (console.log(`  ${ok ? "PASS" : "FAIL"}  ${l}${d ? " — " + d : ""}`), ok || fails++);

const before = sql(`select enabled from integration_connection where provider_key='gis_esri'`);
const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1440, height: 1600 } });
try {
  console.log(`DEF-MET-5624 · bundle at ${BASE}, gis_esri enabled=${before}`);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await p.fill("#signin-email", "dana@brazosbendutilities.com");
  await p.fill("#signin-password", "S3cure!passw0rd");
  await p.click('button[type="submit"]');
  await p.waitForTimeout(2500);

  console.log("\nA · A UTILITY THAT HAS A CITY");
  await p.goto(`${BASE}/${T}/premises/new?step=2`, { waitUntil: "networkidle" });
  await p.waitForTimeout(3000);
  await p.screenshot({ path: "/tmp/cr115-run-now/10-with-city.png", fullPage: true });
  say("the city-map panel is drawn", (await p.locator('[data-testid="found-on-the-city-map"]').count()) === 1);
  say("and the street box is there either way", (await p.locator("#address_line").count()) === 1);

  console.log("\nB · THE SAME UTILITY WITH THE CONNECTOR SWITCHED OFF");
  sql(`update integration_connection set enabled=false where provider_key='gis_esri'`);
  await p.goto(`${BASE}/${T}/premises/new?step=2`, { waitUntil: "networkidle" });
  await p.waitForTimeout(3000);
  await p.screenshot({ path: "/tmp/cr115-run-now/11-no-city.png", fullPage: true });
  const panel = await p.locator('[data-testid="found-on-the-city-map"]').count();
  say("NO city-map panel at all", panel === 0, panel ? `${panel} drawn` : "");
  say("no `Change these`, no `Mark checked`",
      (await p.getByText("Change these").count()) === 0 && (await p.getByText("Mark checked").count()) === 0);
  say("creation is NOT blocked — the form and its fields are all still there",
      (await p.locator("#address_line").count()) === 1 && (await p.locator("#postal_code").count()) === 1
      && (await p.getByRole("button", { name: /Continue/i }).count()) > 0);
} finally {
  sql(`update integration_connection set enabled='${before}'::boolean where provider_key='gis_esri'`);
  const back = sql(`select enabled from integration_connection where provider_key='gis_esri'`);
  console.log(`\n  >> gis_esri enabled RESTORED: ${back}`);
  if (back !== before) { console.log("  FAIL  the connector was not put back"); fails++; }
  await b.close().catch(() => {});
}
console.log(`\n${fails === 0 ? "ALL CHECKS PASSED" : fails + " CHECK(S) FAILED"}`);
process.exit(fails === 0 ? 0 : 1);
