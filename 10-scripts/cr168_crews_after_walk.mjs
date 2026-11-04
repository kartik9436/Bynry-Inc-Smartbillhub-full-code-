// CR-168-BRC10 round 4, lane CREWS — the AFTER walk at 1440 wide, in the states
// images 25–34 draw: the three lists (25, 27, 28), Add crew member (26), Add a
// crew (29), Add a contractor (30), one technician's Overview, Jobs,
// Certifications and Performance (31–34), plus a run-out certification shown as
// a WARNING (PO answer 2 of 2026-10-04).
//
// Run against a PostgreSQL-backed API and the built SPA (`node server.mjs`):
//   BASE=http://127.0.0.1:5581 OUT=08-qa/work-2026-10-04/after node 10-scripts/cr168_crews_after_walk.mjs
// Preconditions: seed_demo + load_sample_data --tenant brazosbend (+ the
// round-2/3 seed scripts named in cr168_capture_work_shapes.py).
//
// WRITES IT MAKES (so a later reader of the database is not misled):
//   * Sam Reyes becomes a technician on Field crew B (job title Field
//     technician, shift 12:00–20:30, van Unit 14);
//   * a crew *Field crew C* (Leak crew, 07:00–15:30, Water I + Excavation) and
//     J. Okoro moves onto it from Field crew B;
//   * a contractor *Hill Country Excavation* (Excavation + Water I, by
//     arrangement, (512) 555-0147, dispatch@hcexcavation.example);
//   * D. Ortiz gains *Backflow tester · 5-yr* to 2031-05-01 and his first
//     certification is renewed to 2029-10-22.
// It reads every write back through the API and prints what it found.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5581";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
// `DRY=1` fills and photographs every form and then presses Cancel — no write
// is made, so the walk can be re-shot on a database it has already written to.
const DRY = process.env.DRY === "1";
async function commit(dialogLocator, name) {
  if (DRY) {
    await dialogLocator.getByRole("button", { name: "Cancel" }).click();
    await settle();
    return false;
  }
  await dialogLocator.getByRole("button", { name }).click();
  await settle(2500);
  return true;
}
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
});
page.on("request", (r) => {
  if (r.url().includes("/api/") && r.method() !== "GET") console.log("WRITE", r.method(), r.url().replace(BASE, ""), r.postData() ?? "");
});
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`=== ${name}.png — ${caption} — ${page.url().replace(BASE, "")}`);
  if (failed.length) console.log("API ERRORS:", JSON.stringify(failed.splice(0)));
}
async function go(path) {
  try {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 });
  } catch {
    console.log("goto timeout", path);
  }
  await settle(1500);
}
const api = (path) =>
  page.evaluate(
    async ([tenant, p]) => {
      const res = await fetch(`/api/${tenant}${p}`, { credentials: "include" });
      return res.ok ? res.json() : { status: res.status };
    },
    [TENANT, path],
  );

// ── sign in ──────────────────────────────────────────────────────────────
await go("/signin");
await page.getByLabel(/email/i).first().fill(EMAIL);
await page.getByLabel(/password/i).first().fill(PASSWORD);
await page.getByRole("button", { name: /sign in/i }).first().click();
await settle(3000);

// ── 25 · Technicians ─────────────────────────────────────────────────────
await go("/work/crews");
await shot("a25-crews-technicians", "Crews · Technicians, the certification watch below");

// ── 26 · Add crew member ─────────────────────────────────────────────────
await page.getByRole("button", { name: "+ Add crew member" }).click();
await settle();
const dialog = page.getByRole("dialog");
await dialog.getByLabel(/Person/).click();
await shot("a26-add-crew-member-picker", "Add crew member — the Person list open, role · status beside each");
await dialog.getByLabel(/Person/).fill("Sam");
await page.getByRole("option", { name: /Sam Reyes/ }).click();
const crews = await api("/work/crews?view=crews&per=50");
const crewB = crews.results.find((row) => row.name === "Field crew B");
await dialog.getByLabel("Crew", { exact: true }).selectOption(crewB.id);
await dialog.getByLabel("Job title").fill("Field technician");
await dialog.locator("#member-shift-start").fill("12:00");
await dialog.locator("#member-shift-end").fill("20:30");
await dialog.getByLabel("Van").fill("Unit 14");
await shot("a26-add-crew-member", "Add crew member — filled, the EFFECT box");
if (await commit(dialog, /Add crew member/)) await shot("a26-add-crew-member-done", "Technicians after the add — Sam Reyes on Field crew B, the badge moved");
const afterMember = await api("/work/crews?view=technicians&q=Sam&per=50");
console.log("READ BACK member:", JSON.stringify(afterMember.results.map((r) => [r.name, r.crew?.name, r.role_label, r.shift])), "counts", JSON.stringify(afterMember.counts));

// ── 27 · Crews ───────────────────────────────────────────────────────────
await go("/work/crews?view=crews");
await shot("a27-crews-crews", "Crews · Crews — both add buttons");

// ── 29 · Add a crew ──────────────────────────────────────────────────────
await page.getByRole("button", { name: "+ Add a crew" }).click();
await settle();
const crewDialog = page.getByRole("dialog");
await crewDialog.getByLabel(/Name/).fill("Field crew C");
await crewDialog.getByLabel("Does").fill("Leak crew");
const techs = await api("/work/crews?view=technicians&per=50");
const okoro = techs.results.find((row) => row.name === "J. Okoro");
await crewDialog.getByLabel("Add a member…").selectOption(okoro.id);
// (on a re-shoot J. Okoro is already on Field crew C, so the EFFECT names C)
const skills = await api("/lookups/work_skills?per=200");
for (const name of ["Water I", "Excavation"]) {
  const skill = skills.results.find((row) => row.name === name);
  await crewDialog.getByLabel("Add a skill…").selectOption(skill.id);
}
await crewDialog.locator("#crew-shift-start").fill("07:00");
await crewDialog.locator("#crew-shift-end").fill("15:30");
await shot("a29-add-a-crew", "Add a crew — filled; EFFECT says J. Okoro leaves Field crew B");
if (await commit(crewDialog, /Add crew/)) await shot("a29-add-a-crew-done", "Crews after the add — Field crew C, 1 person");
const afterCrew = await api("/work/crews?view=crews&per=50");
console.log("READ BACK crews:", JSON.stringify(afterCrew.results.map((r) => [r.name, r.members, r.role_label, r.shift, r.skills.map((s) => s.name)])));

// ── 28 · Contractors ─────────────────────────────────────────────────────
await go("/work/crews?view=contractors");
await shot("a28-crews-contractors", "Crews · Contractors — only + Add a contractor");

// ── 30 · Add a contractor ────────────────────────────────────────────────
await page.getByRole("button", { name: "+ Add a contractor" }).click();
await settle();
const cDialog = page.getByRole("dialog");
await cDialog.getByLabel(/Name/).fill("Hill Country Excavation");
for (const name of ["Excavation", "Water I"]) {
  const skill = skills.results.find((row) => row.name === name);
  await cDialog.getByLabel("Add a skill…").selectOption(skill.id);
}
await cDialog.getByLabel("Phone").fill("(512) 555-0147");
await cDialog.getByLabel("Email").fill("dispatch@hcexcavation.example");
await shot("a30-add-a-contractor", "Add a contractor — filled, By arrangement");
if (await commit(cDialog, /Add contractor/)) await shot("a30-add-a-contractor-done", "Contractors after the add — Hill Country Excavation");
const afterContractor = await api("/work/crews?view=contractors&per=50");
console.log("READ BACK contractors:", JSON.stringify(afterContractor.results.map((r) => [r.name, r.shift, r.phone, r.email, r.skills.map((s) => s.name)])));

// ── 31–34 · one technician ───────────────────────────────────────────────
await go("/work/crews/d-ortiz");
await shot("a31-technician-overview", "D. Ortiz · Overview — Skills, Certifications, This month");
await go("/work/crews/d-ortiz?tab=jobs");
await shot("a32-technician-jobs", "D. Ortiz · Jobs — All");
await page.getByRole("tab", { name: "Done" }).click();
await shot("a32-technician-jobs-done", "D. Ortiz · Jobs — Done");
await go("/work/crews/d-ortiz?tab=certifications");
await shot("a33-technician-certifications", "D. Ortiz · Certifications — the table");
await page.getByRole("button", { name: "+ Add certification" }).click();
await settle();
const certDialog = page.getByRole("dialog");
const types = await api("/lookups/certification_types?per=200");
const heldNow = new Set((await api("/work/technicians/d-ortiz")).certifications.map((c) => c.certification_type_id));
const backflow =
  types.results.find((row) => row.name.startsWith("Backflow") && !heldNow.has(row.id)) ??
  types.results.find((row) => !heldNow.has(row.id));
await certDialog.getByLabel(/Certification/).selectOption(backflow.id);
await certDialog.getByLabel(/Expires/).fill("2031-05-01");
await shot("a33-add-certification", "Add certification — Backflow tester to 2031-05-01");
await commit(certDialog, /Add certification/);
await page.getByRole("button", { name: "Renew" }).first().click();
await settle();
const renewDialog = page.getByRole("dialog");
await renewDialog.getByLabel(/Expires/).fill("2029-10-22");
await shot("a33-renew-certification", "Renew — a new expiry date");
if (await commit(renewDialog, /Renew/)) await shot("a33-technician-certifications-after", "Certifications after add and renew");
const ortiz = await api("/work/technicians/d-ortiz");
console.log("READ BACK certs:", JSON.stringify(ortiz.certifications.map((c) => [c.name, c.expires_on])));
await go("/work/crews/j-okoro?tab=certifications");
await shot("a33-lapsed-certification-warns", "J. Okoro · a run-out certification is a WARNING");
await go("/work/crews/d-ortiz?tab=performance");
await shot("a34-technician-performance", "D. Ortiz · Performance — this month");

await browser.close();
