// CR-168-BRC10 round 6, lane CREWS-2 — the walk at 1440 wide, on PostgreSQL 16,
// of the three things lane SRV-4 serves that the Crews screens now draw:
//   image 27 — a crew's members BY NAME (*D. Ortiz · R. Patel · 2 people*);
//   image 26 — the crew beside each login on Add crew member's Person list;
//   image 33 — the PROOF column: attach a scan (PDF or photo, ≤ 10 MB) on Edit,
//              and open it;
// and DEF-WRK-9640 — Performance with the period set to All time.
//
//   BASE=http://127.0.0.1:5207 OUT=08-qa/work-2026-10-04/after node 10-scripts/cr168_crews2_walk.mjs
// Preconditions: seed_demo + load_sample_data --tenant brazosbend.
//
// WRITES IT MAKES (so a later reader of the database is not misled):
//   * D. Ortiz's first certification gets a PDF proof (`first-aid-card.pdf`),
//     its second a PNG photo (`traffic-card.png`), each through Edit with the
//     expiry date unchanged;
//   * a 12-byte text file is offered and refused on screen (nothing sent).
// It reads every write back through the API and prints what it found.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { deflateSync } from "node:zlib";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5207";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
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

/** A real 40×24 PNG (a card-coloured rectangle), so the server's image probe passes. */
function pngCard() {
  const w = 40, h = 24;
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const c = Buffer.alloc(4); c.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, c]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) raw.set([230, 120, 40], y * (w * 3 + 1) + 1 + x * 3);
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0)),
  ]);
}
const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
    "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n",
);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
});
page.on("request", (r) => {
  if (r.url().includes("/api/") && r.method() !== "GET") console.log("WRITE", r.method(), r.url().replace(BASE, ""));
});
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function shot(name, caption, target = page) {
  await settle();
  await target.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`=== ${name}.png — ${caption} — ${target.url().replace(BASE, "")}`);
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

// ── 27 · Crews, members by name ──────────────────────────────────────────
await go("/work/crews?view=crews");
await shot("crews2-27-crews-member-names", "Crews · Crews — each crew's members by name, then the count");
const crews = await api("/work/crews?view=crews&per=50");
console.log("READ crews:", JSON.stringify(crews.results.map((r) => [r.name, r.member_names, r.members])));
const cells = await page.locator("[data-crew-member-names]").allTextContents();
console.log("ON SCREEN members:", JSON.stringify(cells));

// ── 26 · the Person list, each login's crew ──────────────────────────────
await go("/work/crews");
await page.getByRole("button", { name: "+ Add crew member" }).click();
await settle();
const dialog = page.getByRole("dialog");
await dialog.getByLabel(/Person/).click();
await shot("crews2-26-person-list", "Add crew member — the Person list, *on Field crew A* beside a crewed login");
console.log("ON SCREEN options:", JSON.stringify(await page.getByRole("option").allTextContents()));
await dialog.getByRole("button", { name: "Cancel" }).click();
await settle();

// ── 33 · the PROOF column, attach and open ───────────────────────────────
const techs = await api("/work/crews?view=technicians&q=Ortiz&per=50");
const ortiz = techs.results.find((r) => r.name === "D. Ortiz");
await go(`/work/crews/${ortiz.slug}?tab=certifications`);
await shot("crews2-33-certifications-before", "Certifications — the PROOF column, a dash where no scan is held");
const before = await api(`/work/technicians/${ortiz.slug}`);
const certs = before.certifications;
console.log("READ before:", JSON.stringify(certs.map((c) => [c.name, c.expires_on, c.proof?.name ?? null])));

async function attach(certName, file, shotName, caption) {
  const row = page.locator("tr", { hasText: certName });
  await row.getByRole("button", { name: "Renew" }).click();
  await settle();
  const d = page.getByRole("dialog");
  await d.getByLabel("Proof").setInputFiles(file);
  await shot(shotName, caption);
  await d.getByRole("button", { name: /Renew/ }).click();
  await settle(2500);
}

// a refused file first — nothing is sent
{
  const row = page.locator("tr", { hasText: certs[0].name });
  await row.getByRole("button", { name: "Renew" }).click();
  await settle();
  const d = page.getByRole("dialog");
  await d.getByLabel("Proof").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not a scan\n") });
  await shot("crews2-33-proof-refused", "Edit — a text file is refused on screen before anything is sent");
  await d.getByRole("button", { name: "Cancel" }).click();
  await settle();
}
await attach(certs[0].name, { name: "first-aid-card.pdf", mimeType: "application/pdf", buffer: PDF },
  "crews2-33-attach-pdf", "Edit — the PDF chosen under Proof");
await attach(certs[1].name, { name: "traffic-card.png", mimeType: "image/png", buffer: pngCard() },
  "crews2-33-attach-photo", "Edit — a photo chosen under Proof");
await shot("crews2-33-certifications-after", "Certifications — both rows name their scan");
const after = await api(`/work/technicians/${ortiz.slug}`);
console.log("READ after:", JSON.stringify(after.certifications.map((c) => [c.name, c.expires_on, c.proof?.name ?? null, c.proof?.bytes ?? null])));

// open the photo: a new tab on our own content route
const [popup] = await Promise.all([
  context.waitForEvent("page"),
  page.getByRole("button", { name: "traffic-card.png" }).click(),
]);
const opened = await popup.waitForLoadState("load").then(() => popup.url());
const probe = await page.evaluate(async (url) => {
  const res = await fetch(url, { credentials: "include" });
  return { status: res.status, type: res.headers.get("content-type"), cache: res.headers.get("cache-control"), bytes: (await res.arrayBuffer()).byteLength };
}, opened);
console.log("OPENED:", opened.replace(BASE, ""), JSON.stringify(probe));
await popup.setViewportSize({ width: 1440, height: 1000 });
await shot("crews2-33-proof-opened", "The photo proof, opened in its own tab", popup);
await popup.close();

// ── 34 · Performance, All time (DEF-WRK-9640) ────────────────────────────
await go(`/work/crews/${ortiz.slug}?tab=performance`);
await page.getByLabel("Period").selectOption({ label: "All time" });
await settle(2000);
await shot("crews2-34-performance-all-time", "Performance — All time reads *To date* under Jobs closed");
console.log("ON SCREEN tiles:", (await page.locator("[data-technician-tiles]").textContent())?.slice(0, 200));

await browser.close();
