#!/usr/bin/env node
// ── nc_e2e_walk_after.mjs ───────────────────────────────────────────────────
//
// THE NEW CONNECTION END-TO-END WEB WALK, part 2 of 2 (PO-approved 2026-10-02).
// Part 1 (`nc_e2e_walk.mjs`) made the building and left its RESULTS json; this
// part walks what happens AFTER Create, on the request page, in a real
// Chromium against a real PostgreSQL 16:
//
//   stage 8   actions — Raise order (form), Add fee, To-do + note, Waiting on,
//             Hold → Resume, Add unit / Add service (where the building asks),
//             Messages preview · Send now · Resend, Take payment
//   stage 9   complete SOME work orders — the crew's result (the handset's own
//             door, `POST /work-orders/{id}/field-result`, after ticking the
//             safety rows) and the ACCEPTANCE pressed on the Work tab
//   stage 10  partial approve — the Approve dialog's warning, what a gate
//             holds, Activate what is ready
//   stage 11  complete the rest and approve everything
//
// Writes `<OUT>/nce2e_<S#>_AFTER.json` and screenshots `nce2e_<S#>_<stage>.png`.
//
//   NCW_BUILD=S1 NCW_OUT=<dir> node 10-scripts/nc_e2e_walk_after.mjs
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.NCW_BASE ?? "http://127.0.0.1:8992").replace(/\/$/, "");
const API = (process.env.NCW_API ?? "http://127.0.0.1:8991").replace(/\/$/, "");
const TENANT = process.env.NCW_TENANT ?? "lakeside";
const EMAIL = process.env.NCW_EMAIL ?? "lena@lakesidejunction.com";
const PASSWORD = process.env.NCW_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.NCW_OUT ?? "/tmp/nce2e";
const BUILD = process.env.NCW_BUILD ?? "S1";
const STAGES = (process.env.NCW_STAGES ?? "8,9,10,11").split(",").map(Number);
const PART1 = JSON.parse(readFileSync(join(OUT, `nce2e_${BUILD}_RESULTS.json`), "utf8"));
const CID = PART1.facts.connectionId;
const NEW_UNIT = process.env.NCW_UNIT_LABEL ?? "9";
// Since PO 2026-10-02 item 1 every build with an owner opens an account that
// pays (a master, or a single-family owner's own regular account).
const HAS_PAYER = true;

// What each building does after Create (the plan's payment mix: cash, cheque
// with a number, card, ACH; one partial, one exact).
const AFTER = {
  S1: { pay: { method: "check", amount: "40.00", ref: "4471" }, addUnit: true, fee: /INSPECT|AFTER-HRS/ },
  S2: { fee: /AFTER-HRS|INSPECT/ }, // paid in full by card at Create: nothing left to take
  S3: { pay: { method: "cash", amount: "exact" }, addService: "gas", fee: null },
  S4: { fee: /INSPECT|AFTER-HRS/ }, // PO 2026-10-02 item 1: the owner's own (Pending) account pays
  S5: {},
  S6: { fee: null },
  S7: { pay: { method: "ach", amount: "exact", ref: "ACH-900114" }, addUnit: true, fee: null },
  S8: { pay: { method: "card", amount: "30.00", ref: "AUTH-S8-0030" }, fee: null },
}[BUILD];

const results = [];
const facts = { build: BUILD, connectionId: CID };
const serverErrors = [];
const record = (verdict, stage, label, evidence = "") => {
  results.push({ verdict, stage, label, evidence: String(evidence).slice(0, 1500) });
  console.log(`${verdict.padEnd(5)} [${stage}] ${label}${evidence === "" ? "" : ` — ${String(evidence).slice(0, 400)}`}`);
};
const check = (stage, label, ok, evidence = "") => record(ok ? "PASS" : "FAIL", stage, label, evidence);
const note = (stage, label, evidence = "") => record("NOTE", stage, label, evidence);

function resolveChromium() {
  const pinned = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  if (existsSync(pinned)) return pinned;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    const c = join("/opt/pw-browsers", dir, "chrome-linux", "chrome");
    if (existsSync(c)) return c;
  }
  throw new Error("no chromium");
}
const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
page.on("response", (r) => {
  if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
});
page.on("pageerror", (e) => serverErrors.push(`pageerror ${e.message}`));

async function shoot(stage) {
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.waitForTimeout(400);
  const need = await page.evaluate(() => {
    const view = document.querySelector(".view");
    return view === null ? null : Math.ceil(view.getBoundingClientRect().top + view.scrollHeight + 24);
  });
  const height = Math.min(Math.max(need ?? 1200, 900), 16000);
  await page.setViewportSize({ width: 1440, height });
  await page.waitForTimeout(400);
  const file = join(OUT, `nce2e_${BUILD}_${stage}.png`);
  await page.screenshot({ path: file });
  const size = statSync(file).size;
  console.log(`      shot ${file} 1440x${height} ${size} bytes`);
  if (size < 20000) record("FAIL", stage, "screenshot looks blank", `${size} bytes`);
  await page.setViewportSize({ width: 1440, height: 1200 });
}
const has = async (s) => (await page.locator(s).count()) > 0;
const viewText = async () => (await page.locator(".view").innerText().catch(() => "")).replace(/\s+/g, " ");
async function open(tab) {
  await page.goto(`${BASE}/${TENANT}/connections/${CID}?tab=${tab}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
}
async function chooseIn(selector, re) {
  const loc = page.locator(selector).first();
  if ((await loc.count()) === 0) return { picked: null, offered: [] };
  const opts = await loc.evaluate((s) =>
    [...s.options].filter((o) => !o.disabled && o.value !== "").map((o) => ({ v: o.value, t: o.textContent.trim() })),
  );
  const hit = opts.find((o) => re.test(o.t) || re.test(o.v));
  if (!hit) return { picked: null, offered: opts.map((o) => o.t) };
  await loc.selectOption(hit.v);
  return { picked: hit.t, offered: opts.map((o) => o.t) };
}
async function submitModal() {
  const wait = page.waitForResponse((r) => r.url().includes("/api/") && r.request().method() !== "GET", { timeout: 30000 }).catch(() => null);
  await page.locator(".modal-foot button").last().click();
  const resp = await wait;
  await page.waitForTimeout(1500);
  const status = resp === null ? "none" : resp.status();
  let body = "";
  try {
    body = resp === null ? "" : (await resp.text()).slice(0, 500);
  } catch {
    body = "";
  }
  const stillOpen = await has(".modal-foot");
  const modalErr = stillOpen ? (await page.locator(".modal, [role=dialog]").first().innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 400) : "";
  return { status, body, stillOpen, modalErr };
}
async function more(act) {
  // The menu is a <details>: a second click on its summary CLOSES it, so open it
  // only when it is shut.
  const isOpen = await page.locator("[data-build-more]").first().evaluate((d) => d.open).catch(() => false);
  if (!isOpen) await page.locator("[data-build-more] > summary").first().click().catch(() => undefined);
  await page.waitForTimeout(400);
  const item = page.locator(`[data-build-more-panel] [data-act="${act}"]`).first();
  if ((await item.count()) === 0) return false;
  if (await item.isDisabled().catch(() => false)) return "disabled";
  await item.click();
  await page.waitForTimeout(700);
  return true;
}
const api = {
  async get(path) {
    const r = await page.request.get(`${API}/api/${TENANT}${path}`);
    return { status: r.status(), json: await r.json().catch(() => null) };
  },
  async post(path, data) {
    const r = await page.request.post(`${API}/api/${TENANT}${path}`, { data });
    return { status: r.status(), json: await r.json().catch(() => null) };
  },
};
const stateWord = async () => (await page.locator("[data-build-detail]").first().innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 200);

// ── sign in (the API calls share the browser's session cookie) ─────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }).catch(() => undefined);
{
  const r = await page.request.post(`${API}/api/${TENANT}/auth/session`, { data: { email: EMAIL, password: PASSWORD } });
  if (r.status() >= 300) note("0", "API session", String(r.status()));
}

// ════ STAGE 8 · actions on the request ══════════════════════════════════════
// NCW_ONLY8=a,f,… runs only those actions (a re-walk after a fix).
const ONLY8 = (process.env.NCW_ONLY8 ?? "a,b,c,d,e,f,g,h").split(",");
const want = (k) => ONLY8.includes(k);
if (STAGES.includes(8)) {
  // 8a · Raise order — the form.
  if (want("a")) {
  await open("work");
  const before = (await api.get(`/connections/${CID}/activation`)).json?.orders_total;
  if (await has('[data-act="raiseOrder"]')) {
    await page.locator('[data-act="raiseOrder"]').first().click();
    await page.waitForTimeout(1200);
    const tpl = await chooseIn("#build-raise-template", /Inspection|Site/);
    const svc = await chooseIn("#build-raise-service", /./);
    const unit = await chooseIn("#build-raise-unit", /^1$|Unit 1|^1 /);
    await page.fill("#build-raise-date", "2026-10-20").catch(() => undefined);
    note("8", "Raise order form", `job ${tpl.picked} · service ${svc.picked} · unit ${unit.picked} (units offered: ${unit.offered.join(", ")})`);
    await shoot("8a_raise_order_form");
    const r = await submitModal();
    const toast = (await page.locator("[role=status], .toast").first().innerText().catch(() => "")).replace(/\s+/g, " ");
    const after = (await api.get(`/connections/${CID}/activation`)).json?.orders_total;
    check("8", "Raise order raises one more work order", r.status < 300 && after === (before ?? 0) + 1, `${r.status} ${toast} · orders ${before} → ${after} ${r.modalErr}`);
    await open("work");
    const due = await viewText();
    check("8", "the raised order shows its target 10/20 (not a day early)", /10\/20\/2026/.test(due), (due.match(/WO-\d+[^W]{0,200}10\/(19|20)\/2026/) ?? [""])[0]);
    await shoot("8a_raise_order_done");
  } else note("8", "no Raise order button on the Work tab", "");
  }

  // 8b · To-do and note.
  if (want("b")) {
  await open("todo");
  await page.locator('[data-act="addTodo"]').click().catch(() => undefined);
  await page.waitForTimeout(500);
  await page.fill("#text", `Collect the meter-room keys (${BUILD})`).catch(() => undefined);
  const t1 = await submitModal();
  await page.locator('[data-act="addNote"]').click().catch(() => undefined);
  await page.waitForTimeout(500);
  await page.fill("#text", `Owner prefers morning visits (${BUILD})`).catch(() => undefined);
  const t2 = await submitModal();
  const kinds = await page.$$eval('[data-table="build-todos"] tbody tr', (trs) => trs.map((t) => t.getAttribute("data-todo-row")));
  check("8", "To-do tab holds a to-do and a note", t1.status < 300 && t2.status < 300 && kinds.includes("todo") && kinds.includes("note"), `${t1.status}/${t2.status} rows ${kinds.join(",")}`);
  await shoot("8b_todo_note");
  }

  // 8c · Waiting on.
  if (want("c")) {
  await open("overview");
  const w = await more("waitingOn");
  if (w === true) {
    await page.fill("#build-act-text", "City permit office").catch(() => undefined);
    const r = await submitModal();
    const hdr = await viewText();
    check("8", "Waiting on is recorded and shown", r.status < 300 && /City permit office/.test(hdr), `${r.status} ${r.modalErr}`);
  } else note("8", "Waiting on not offered", String(w));
  await shoot("8c_waiting_on");
  }

  // 8d · Hold → Resume.
  if (want("d")) {
  const h = await more("hold");
  if (h === true) {
    await page.fill("#build-act-text", "Owner asked to pause for financing").catch(() => undefined);
    const r = await submitModal();
    await open("overview");
    const st = await viewText();
    check("8", "Hold puts the request On hold", r.status < 300 && /On hold/i.test(st), `${r.status} ${r.modalErr}`);
    await shoot("8d_on_hold");
    const appr = page.locator('[data-act="approve"]');
    const disabled = (await appr.count()) > 0 ? await appr.isDisabled() : null;
    note("8", "Approve while on hold", `disabled=${disabled} title=${await appr.getAttribute("title").catch(() => "")}`);
    const rel = await more("release");
    if (rel === true) {
      if (await has("#build-act-text")) await page.fill("#build-act-text", "Financing approved").catch(() => undefined);
      const r2 = (await has(".modal-foot")) ? await submitModal() : { status: 200 };
      await open("overview");
      const st2 = await viewText();
      check("8", "Resume takes it off hold", r2.status < 300 && !/On hold/i.test(st2.slice(0, 300)), `${r2.status}`);
    } else check("8", "Resume offered while on hold", false, String(rel));
  } else note("8", "Hold not offered", String(h));
  }

  // 8e · Add unit / Add service.
  if ((AFTER.addUnit || AFTER.addService) && want("e")) await open("overview");
  if (AFTER.addUnit && want("e")) {
    const a = await more("addUnit");
    if (a === true) {
      await page.fill("#label", NEW_UNIT).catch(() => undefined);
      // Unit type is a SELECT once DEF fixed below lands, a free-text box before.
      const tag = await page.locator("#unit_type").evaluate((n) => n.tagName).catch(() => "");
      note("8", "Add unit: the Unit type control", tag === "SELECT" ? "a list of the utility's unit types" : `free text (${tag})`);
      if (tag === "SELECT") await chooseIn("#unit_type", /Residential|Commercial/);
      else await page.fill("#unit_type", "residential").catch(() => undefined);
      // First press with NO service ticked: what does the form say?
      const r0 = await submitModal();
      note("8", "Add unit pressed with no service ticked", `${r0.status} still open=${r0.stillOpen} :: ${r0.modalErr}`);
      for (const code of ["electric", "water"]) {
        await page.locator(`#service-${code}`).check({ force: true }).catch(() => undefined);
      }
      const ticked = await page.$$eval('[data-field="services"] input[type=checkbox]', (ns) => ns.filter((n) => n.checked).map((n) => n.id));
      note("8", "Add unit services ticked", ticked.join(","));
      await shoot("8e_add_unit_form");
      const r = await submitModal();
      const act = (await api.get(`/connections/${CID}/activation`)).json;
      const labels = [...new Set((act?.rows ?? []).map((x) => x.unit_label))];
      check("8", `Add unit makes unit ${NEW_UNIT} with its services`, r.status < 300 && labels.includes(NEW_UNIT), `${r.status} units ${labels.join(",")} ${r.modalErr}`);
    } else note("8", "Add unit not offered", String(a));
  }
  if (AFTER.addService && want("e")) {
    const a = await more("addService");
    if (a === true) {
      const s = await chooseIn("#service", new RegExp(AFTER.addService, "i"));
      const u = await chooseIn("#unit", /./);
      await shoot("8e_add_service_form");
      const r = await submitModal();
      const act = (await api.get(`/connections/${CID}/activation`)).json;
      const svcs = [...new Set((act?.rows ?? []).map((x) => x.service))];
      check("8", `Add service adds ${AFTER.addService}`, r.status < 300 && svcs.includes(AFTER.addService), `${r.status} picked ${s.picked}/${u.picked} services ${svcs.join(",")} ${r.modalErr}`);
    } else note("8", "Add service not offered", String(a));
  }

  // 8f · Add fee (to the build's owner account).
  if (HAS_PAYER && AFTER.fee && want("f")) {
    await open("charges");
    const before2 = await viewText();
    await page.locator('[data-act="addFee"]').click().catch(() => undefined);
    await page.waitForTimeout(800);
    const c = await chooseIn("#build-fee-code", AFTER.fee);
    if (await has("#build-fee-each")) await page.fill("#build-fee-each", "30.00").catch(() => undefined);
    if (await has("#build-fee-amount")) await page.fill("#build-fee-amount", "30.00").catch(() => undefined);
    await page.fill("#build-fee-date", "2026-10-03").catch(() => undefined);
    await chooseIn("#build-fee-terms", /30/);
    const basis = await chooseIn("#build-fee-basis", /premise|build|unit/i);
    note("8", "Add fee: Counted per", `${basis.picked} (offered: ${basis.offered.join(", ")})`);
    await shoot("8f_add_fee_form");
    const r = await submitModal();
    await open("charges");
    const after2 = await viewText();
    note("8", "Charges tab before / after the fee", `${before2.match(/CHARGED [\d,.]+/)?.[0]} → ${after2.match(/CHARGED [\d,.]+/)?.[0]}`);
    check("8", `Add fee (${c.picked}) issues a second bill`, r.status < 300 && before2.match(/CHARGED [\d,.]+/)?.[0] !== after2.match(/CHARGED [\d,.]+/)?.[0], `${r.status} ${r.body.slice(0, 200)} ${r.modalErr}`);
    facts.feeResponse = r.body;
    await shoot("8f_fee_added");
  }

  // 8g · Messages: preview, Send now, Resend.
  if (want("g")) {
  await open("messages");
  const rows = await page.$$eval("[data-message-row]", (ns) => ns.map((n) => ({ code: n.getAttribute("data-message-row"), text: n.innerText.replace(/\s+/g, " ") })));
  facts.messagesBefore = rows;
  note("8", "Messages tab before sending", rows.map((r) => `${r.code}: ${r.text}`).join(" ‖ "));
  const first = page.locator('[data-message-row="build_created"]').first();
  if ((await first.count()) > 0) {
    const eye = first.locator("button").first();
    await eye.click().catch(() => undefined);
    await page.waitForTimeout(1500);
    const subject = (await page.locator("[data-preview-subject]").first().innerText().catch(() => "")).trim();
    const body = (await page.locator("[data-preview-body]").first().innerText().catch(() => "")).replace(/\s+/g, " ");
    facts.previewBuildConfirmed = { subject, body: body.slice(0, 1200) };
    check("8", "Preview shows the rendered letter", subject !== "" || body !== "", `${subject} | ${body.slice(0, 300)}`);
    await shoot("8g_message_preview");
    await page.locator("[data-preview-close]").first().click().catch(() => page.keyboard.press("Escape"));
    await page.waitForTimeout(500);
    for (const pass of ["send", "resend"]) {
      const send = page.locator('[data-message-row="build_created"] button').nth(1);
      const wait = page.waitForResponse((r) => /\/messages\/.+\/send/.test(r.url()), { timeout: 20000 }).catch(() => null);
      await send.click().catch(() => undefined);
      await page.waitForTimeout(600);
      if (await has(".modal-foot")) await page.locator(".modal-foot button").last().click().catch(() => undefined);
      const resp = await wait;
      const txt = resp === null ? "no request" : `${resp.status()} ${(await resp.text().catch(() => "")).slice(0, 300)}`;
      check("8", `Messages: ${pass === "send" ? "Send now" : "Resend"} on Build confirmed`, resp !== null && resp.status() < 300, txt);
      await page.waitForTimeout(1200);
    }
    await open("messages");
    const after = await page.$$eval("[data-message-row]", (ns) => ns.map((n) => ({ code: n.getAttribute("data-message-row"), text: n.innerText.replace(/\s+/g, " ") })));
    facts.messagesAfterSend = after;
    note("8", "Messages tab after Send now + Resend", after.map((r) => `${r.code}: ${r.text}`).join(" ‖ "));
    await shoot("8g_messages_after_send");
  }

  }

  // 8h · Take payment (after Create).
  if (HAS_PAYER && AFTER.pay && want("h")) {
    await open("charges");
    const rec = (await api.get(`/connections/${CID}/record`)).json;
    const outstanding = rec?.money?.outstanding?.display ?? rec?.tiles?.outstanding?.display;
    let amount = AFTER.pay.amount;
    if (amount === "exact") amount = String(outstanding ?? "").replace(/,/g, "");
    if (amount === "exact-fee") amount = "30.00";
    if (AFTER.pay.method === "cash" || AFTER.pay.method === "check") {
      // A till must be open for cash or a cheque (BR-PAY-1186): Payments › Start counter.
      const mine = await api.get("/counters?mine=open");
      const openOne = (mine.json?.results ?? []).find((c) => c.closed_at === null);
      if (!openOne) {
        await page.goto(`${BASE}/${TENANT}/payments`, { waitUntil: "networkidle" });
        await page.waitForTimeout(1500);
        const start = page.getByRole("button", { name: /Start counter/ }).or(page.getByRole("link", { name: /Start counter/ }));
        if ((await start.count()) > 0) {
          await start.first().click();
          await page.waitForTimeout(1000);
          await chooseIn("#service_centre", /./);
          await page.fill("#opening_float", "100.00").catch(() => undefined);
          await shoot("8h_start_counter");
          const r = await submitModal();
          check("8", "Start counter opens a till for cash and cheques", r.status < 300, `${r.status} ${r.body.slice(0, 200)} ${r.modalErr}`);
        } else note("8", "no Start counter control on Payments", "");
        await open("charges");
      }
    }
    await page.locator('[data-act="takePayment"]').first().click().catch(() => undefined);
    await page.waitForTimeout(1200);
    const m = await chooseIn("#method", new RegExp(`^${AFTER.pay.method}$|${{ check: "Check", ach: "ACH", cash: "Cash", card: "Card" }[AFTER.pay.method]}`, "i"));
    await page.fill("#amount", amount).catch(() => undefined);
    if (AFTER.pay.ref && (await has("#confirmation"))) await page.fill("#confirmation", AFTER.pay.ref).catch(() => undefined);
    await page.fill("#memo", `NC walk ${BUILD} ${AFTER.pay.method}`).catch(() => undefined);
    await shoot("8h_take_payment_form");
    const r = await submitModal();
    facts.takePayment = { method: m.picked, amount, ref: AFTER.pay.ref ?? null, status: r.status, body: r.body, outstandingBefore: outstanding };
    check("8", `Take payment ${m.picked} ${amount}${AFTER.pay.ref ? ` #${AFTER.pay.ref}` : ""}`, r.status < 300, `${r.status} ${r.body.slice(0, 300)} ${r.modalErr}`);
    await open("charges");
    const ch = await viewText();
    note("8", "Charges tab after the payment", ch.slice(ch.indexOf("CHARGED"), ch.indexOf("CHARGED") + 900));
    await shoot("8h_charges_after_payment");
  }
}

// ── the crew's result for one order, then the acceptance ───────────────────
async function crewCompletes(order, outcome = "passed") {
  const d = (await api.get(`/work-orders/${order.id}/checklist`)).json ?? {};
  for (const s of d.safety ?? []) {
    if (s.ticked_at) continue;
    await api.post(`/work-orders/${order.id}/safety/${s.id}/tick`, {});
  }
  for (const s of d.tasks ?? []) {
    if (s.ticked_at) continue;
    const r = await api.post(`/work-orders/${order.id}/tasks/${s.id}/tick`, {});
    if (r.status >= 300) facts.taskTickRefusals = [...(facts.taskTickRefusals ?? []), `${order.order_no}: ${r.status} ${JSON.stringify(r.json).slice(0, 160)}`];
  }
  return api.post(`/work-orders/${order.id}/field-result`, {
    outcome,
    field_data: { completed_on: "2026-10-02", note: `NC walk ${BUILD}` },
    external_ref: `CREW-${order.order_no ?? order.id.slice(0, 6)}`,
  });
}
async function acceptOnWorkTab(order) {
  await open("work");
  const row = page.locator("tbody tr", { hasText: order.order_no }).first();
  if ((await row.count()) === 0) return { ok: false, why: "row not on the Work tab" };
  await row.locator("button, a").last().click().catch(() => undefined);
  await page.waitForTimeout(1200);
  const accept = page.getByRole("button", { name: /^(Accept|Mark complete)/ }).first();
  if ((await accept.count()) === 0) return { ok: false, why: "no Accept button in the order panel" };
  const wait = page.waitForResponse((r) => /\/accept$/.test(r.url()), { timeout: 20000 }).catch(() => null);
  await accept.click();
  const resp = await wait;
  await page.waitForTimeout(1500);
  return { ok: resp !== null && resp.status() < 300, why: resp === null ? "no request" : `${resp.status()} ${(await resp.text()).slice(0, 300)}` };
}
async function ordersOf() {
  const act = (await api.get(`/connections/${CID}/activation`)).json ?? {};
  const seen = new Map();
  for (const row of act.rows ?? []) for (const w of row.work_orders ?? []) seen.set(w.id, { ...w, service: w.service ?? row.service });
  return { act, orders: [...seen.values()] };
}

// ════ STAGE 9 · complete SOME work orders ═══════════════════════════════════
if (STAGES.includes(9)) {
  const { act, orders } = await ordersOf();
  facts.ordersBefore = orders.map((o) => `${o.order_no}:${o.service}:${o.state ?? o.status}`);
  // the FIRST service's orders, all of them — so that one service becomes ready.
  const services = [...new Set((act.rows ?? []).map((r) => r.service))];
  const pick = services.includes("electric") ? "electric" : services[0];
  facts.firstService = pick;
  const some = orders.filter((o) => o.service === pick);
  let firstAccepted = false;
  for (const o of some) {
    const fr = await crewCompletes(o);
    check("9", `crew result on ${o.order_no} (${pick})`, fr.status < 300, `${fr.status} ${JSON.stringify(fr.json).slice(0, 300)}`);
    if (!firstAccepted) {
      const a = await acceptOnWorkTab(o);
      check("9", `Accept pressed on the Work tab for ${o.order_no}`, a.ok, a.why);
      await shoot("9_accept_on_work_tab");
      firstAccepted = true;
    } else {
      const a = await api.post(`/work-orders/${o.id}/accept`, {});
      check("9", `accept ${o.order_no}`, a.status < 300, `${a.status} ${JSON.stringify(a.json).slice(0, 300)}`);
    }
  }
  await open("work");
  await shoot("9_work_tab_some_done");
}

// ════ STAGE 10 · partial approve ════════════════════════════════════════════
if (STAGES.includes(10)) {
  await open("units");
  await shoot("10a_units_before_approve");
  const appr = page.locator('[data-act="approve"]').first();
  const disabled = await appr.isDisabled().catch(() => true);
  note("10", "Approve button", `disabled=${disabled} title=${await appr.getAttribute("title").catch(() => "")}`);
  if (!disabled) {
    await appr.click();
    await page.locator("[data-activate-dialog]").waitFor({ timeout: 15000 }).catch(() => undefined);
    const dlg = (await page.locator("[data-activate-dialog]").innerText().catch(() => "")).replace(/\s+/g, " ");
    facts.approveDialogPartial = dlg;
    check("10", "the Approve dialog warns about open orders", /not complete|open/i.test(dlg), dlg.slice(0, 600));
    const gated = (await page.locator("[data-activate-gated]").innerText().catch(() => "")).replace(/\s+/g, " ");
    note("10", "what a gate holds back", gated.slice(0, 500));
    await shoot("10b_approve_warning");
    const ready = page.locator('[data-act="activateReady"] button, button[data-act="activateReady"], [data-act="activateReady"]').first();
    const readyDisabled = await ready.isDisabled().catch(() => null);
    if (readyDisabled === false || (await ready.locator("button").count()) > 0) {
      const wait = page.waitForResponse((r) => /\/activate$/.test(r.url()), { timeout: 30000 }).catch(() => null);
      await (await ready.locator("button").count() > 0 ? ready.locator("button").first() : ready).click();
      const resp = await wait;
      const txt = resp === null ? "no request" : `${resp.status()} ${(await resp.text()).slice(0, 400)}`;
      check("10", "Activate what is ready", resp !== null && resp.status() < 300, txt);
    } else note("10", "nothing ready to activate", "");
    await page.waitForTimeout(1500);
  }
  await open("units");
  const st = await viewText();
  facts.stateAfterPartial = st.slice(0, 200);
  check("10", "the request reads Partly activated", /Partly activated/i.test(st), st.slice(0, 200));
  await shoot("10c_partly_activated");
}

// ════ STAGE 11 · complete the rest, approve all ═════════════════════════════
if (STAGES.includes(11)) {
  const { orders } = await ordersOf();
  for (const o of orders) {
    const s = String(o.state ?? o.status ?? "");
    if (/complete|accepted|done/i.test(s)) continue;
    const fr = await crewCompletes(o);
    const a = await api.post(`/work-orders/${o.id}/accept`, {});
    if (fr.status >= 300 || a.status >= 300) record("FAIL", "11", `complete + accept ${o.order_no}`, `${fr.status} ${JSON.stringify(fr.json).slice(0, 200)} / ${a.status} ${JSON.stringify(a.json).slice(0, 200)}`);
  }
  await open("units");
  const appr = page.locator('[data-act="approve"]').first();
  if ((await appr.count()) > 0 && !(await appr.isDisabled())) {
    await appr.click();
    await page.locator("[data-activate-dialog]").waitFor({ timeout: 15000 }).catch(() => undefined);
    const dlg = (await page.locator("[data-activate-dialog]").innerText().catch(() => "")).replace(/\s+/g, " ");
    facts.approveDialogAll = dlg;
    await shoot("11a_approve_all_dialog");
    const ready = page.locator('[data-act="activateReady"]').first();
    const btn = (await ready.locator("button").count()) > 0 ? ready.locator("button").first() : ready;
    const wait = page.waitForResponse((r) => /\/activate$/.test(r.url()), { timeout: 30000 }).catch(() => null);
    await btn.click().catch(() => undefined);
    const resp = await wait;
    check("11", "Approve everything that is ready", resp !== null && resp.status() < 300, resp === null ? "no request" : `${resp.status()} ${(await resp.text()).slice(0, 400)}`);
    await page.waitForTimeout(1500);
  } else note("11", "Approve not available", await appr.getAttribute("title").catch(() => ""));
  await open("overview");
  const st = await viewText();
  facts.stateAfterAll = st.slice(0, 200);
  check("11", "the request reads Activated", /Activated/i.test(st) && !/Partly activated/i.test(st.slice(0, 200)), st.slice(0, 200));
  await shoot("11b_activated");
  await open("units");
  await shoot("11c_units_activated");
  await open("messages");
  facts.messagesAfterApproval = await page.$$eval("[data-message-row]", (ns) => ns.map((n) => n.innerText.replace(/\s+/g, " ")));
  note("11", "Messages tab after approval", facts.messagesAfterApproval.join(" ‖ "));
  await shoot("11d_messages_after_approval");
}

for (const e of serverErrors) record("FAIL", "any", "5xx or page error during the walk", e);
writeFileSync(join(OUT, `nce2e_${BUILD}_AFTER.json`), JSON.stringify({ facts, results, serverErrors }, null, 2));
await browser.close();
const failed = results.filter((r) => r.verdict === "FAIL").length;
console.log(`── ${BUILD} after: ${results.length} checks, ${failed} FAIL`);
