// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — the phases of `cf_e2e_walk.mjs` (the ONE end-to-end
//          custom-fields walk). Read that file's header first; this one only
//          holds the story, phase by phase, in the order a utility lives.
// ───────────────────────────────────────────────────────

export function makePhases(H) {
  const { ok, shot, state, dialog, norm, signIn, CF, listFields, addFieldViaSettings, placeViaSettings, A, B, C,
    A_FIELDS, SEU_FIELDS } = H;

  const pages = {};
  async function page(ctx, who) {
    if (!pages[who.t] || pages[who.t].isClosed()) {
      pages[who.t] = await signIn(ctx.browser, who);
      ctx.pages[who.t] = pages[who.t];
    }
    return pages[who.t];
  }
  const cfUrl = (t, q) => `${CF(t)}${q ? `&q=${encodeURIComponent(q)}` : ""}`;
  async function rowFor(p, label) {
    await p.goto(cfUrl(p.who.t, label), { waitUntil: "networkidle" });
    await p.waitForTimeout(600);
    return p.locator("tr", { hasText: label }).first();
  }
  async function fieldByKey(p, entity, key) {
    return (await listFields(p)).find((r) => r.entity === entity && r.key === key);
  }

  /** The five Settings rules, checked in ONE utility through its own screens. */
  async function settingsRules(p, tag, { entity, firstLabel, tidy = true }) {
    const t = p.who.t;
    // R1 — max 10 ACTIVE per record type: fill to ten, the eleventh refused.
    const mine = (await listFields(p)).filter((r) => r.entity === entity && r.is_active);
    const fillers = [];
    for (let i = mine.length; i < 10; i += 1) {
      const made = await p.api("POST", "/settings/custom-fields", { entity, label: `${tag} filler ${i + 1}`, data_type: "text" });
      ok(`${t}: filler ${i + 1} on ${entity} accepted (${i + 1} of 10)`, made.status === 201, made.text.slice(0, 200));
      fillers.push(made.body);
    }
    const active = (await listFields(p)).filter((r) => r.entity === entity && r.is_active).length;
    ok(`${t}: ${entity} holds exactly 10 active fields`, active === 10, String(active), ["rules", `${t} · 11th refused`, "pass"]);
    await p.goto(CF(t), { waitUntil: "networkidle" });
    await p.locator("button", { hasText: "+ Add custom field" }).first().click();
    await dialog(p).waitFor();
    await p.fill("#label", `${tag} eleventh`);
    await p.selectOption("#entity", entity === "areas" ? { label: "Areas" } : { label: "Premises" });
    const head = norm(await p.locator("#entity-help").textContent().catch(() => ""));
    ok(`${t}: the dialog says no room is left`, /0/.test(head), head, ["rules", `${t} · 11th refused`, "pass"]);
    const refusedAns = p.waitForResponse((r) => r.url().endsWith("/settings/custom-fields") && r.request().method() === "POST");
    await dialog(p).locator('button[data-variant="primary"]').last().click();
    const refused = await refusedAns;
    await p.waitForTimeout(600);
    const why = norm(await dialog(p).textContent().catch(() => ""));
    ok(`${t}: the 11th active ${entity} field is refused on screen`, refused.status() === 422 && (await dialog(p).count()) === 1, `${refused.status()} ${why.slice(0, 300)}`, ["rules", `${t} · 11th refused`, "pass"]);
    await shot(p, `${tag}_r1_eleventh_refused`);
    await dialog(p).getByRole("button", { name: "Cancel" }).click();
    // R2 — switching one off frees its slot.
    const first = fillers[0] ?? mine.find((r) => r.label !== firstLabel);
    const row = await rowFor(p, first.label);
    await row.locator('button[aria-label="Deactivate"]').click();
    await p.waitForTimeout(1200);
    const after = (await listFields(p)).find((r) => r.id === first.id);
    ok(`${t}: Deactivate switches ${first.label} off`, after && after.is_active === false, JSON.stringify(after).slice(0, 200), ["rules", `${t} · off frees a slot`, "pass"]);
    const now = await p.api("POST", "/settings/custom-fields", { entity, label: `${tag} eleventh`, data_type: "text" });
    ok(`${t}: with one off, the same field is accepted`, now.status === 201, now.text.slice(0, 200), ["rules", `${t} · off frees a slot`, "pass"]);
    // R3 — no delete, anywhere.
    const actions = norm(await (await rowFor(p, firstLabel)).innerText());
    ok(`${t}: the row offers no Delete`, !/Delete|Remove/i.test(actions) && (await p.locator('button[aria-label*="Delete"]').count()) === 0, actions, ["rules", `${t} · no delete`, "pass"]);
    const del = await p.api("DELETE", `/settings/custom-fields/${first.id}`);
    ok(`${t}: DELETE is not a verb the API has`, del.status === 405 || del.status === 404, `${del.status}`, ["rules", `${t} · no delete`, "pass"]);
    // R4 — the key cannot be renamed.
    const firstRow = (await listFields(p)).find((r) => r.label === firstLabel);
    await (await rowFor(p, firstLabel)).locator('button[aria-label="Edit"]').click();
    await dialog(p).waitFor();
    ok(`${t}: Edit shows the key read-only`, (await p.locator("#key").getAttribute("readonly")) !== null, "", ["rules", `${t} · key not renamed`, "pass"]);
    await shot(p, `${tag}_r4_key_read_only`);
    await dialog(p).getByRole("button", { name: "Cancel" }).click();
    const rename = await p.api("PATCH", `/settings/custom-fields/${firstRow.id}`, { key: "renamed_key" });
    ok(`${t}: renaming the key is refused by name`, rename.status === 422 && rename.text.includes("immutable_after_create"), rename.text.slice(0, 200), ["rules", `${t} · key not renamed`, "pass"]);
    // tidy: the fillers and the eleventh go off again (they are kept, never deleted).
    if (tidy) await tidyFillers(p, tag);
    return { fillers };
  }
  async function tidyFillers(p, tag) {
    const extra = (await listFields(p)).filter((r) => r.label.startsWith(`${tag} `) && r.is_active);
    for (const f of extra) await p.api("PATCH", `/settings/custom-fields/${f.id}`, { active: false });
  }

  /** R5 — shown but never collected warns, unless an import feeds it. */
  async function viewWithoutInput(p, tag) {
    const t = p.who.t;
    let probe = await fieldByKey(p, "accounts", `${tag}_view_only_probe`);
    if (!probe) probe = (await p.api("POST", "/settings/custom-fields", { entity: "accounts", label: `${tag} view only probe`, key: `${tag}_view_only_probe`, data_type: "text" })).body;
    const r = await placeViaSettings(p, probe.label, { S18: "not_shown", S21: "view" }, { expectRefusal: true });
    ok(`${t}: an account field shown on Account detail and collected nowhere is refused: "No screen collects this field."`,
      r.refused && r.after.includes("No screen collects this field."), r.after.slice(0, 300), ["rules", `${t} · view-only warns`, "pass"]);
    const others = (await listFields(p)).filter((f) => f.label !== probe.label).map((f) => f.label);
    ok(`${t}: the warning names no other field (none of this utility's, none of another's)`,
      !others.some((l) => r.after.includes(l)) && !/Roof|Loyalty|DTE|Generator/.test(r.after), r.after.slice(0, 300), ["rules", `${t} · view-only warns`, "pass"]);
    let imp = await fieldByKey(p, "premises", `${tag}_import_fed_probe`);
    if (!imp) imp = (await p.api("POST", "/settings/custom-fields", { entity: "premises", label: `${tag} import fed probe`, key: `${tag}_import_fed_probe`, data_type: "text" })).body;
    const r2 = await placeViaSettings(p, imp.label, { PREMISE_PAGE: "view" });
    ok(`${t}: a premises field fed by the import may be View-only`, !r2.refused && r2.text.includes("Filled by import."), r2.text.slice(0, 300), ["rules", `${t} · view-only warns`, "pass"]);
    for (const f of [probe, imp]) await p.api("PATCH", `/settings/custom-fields/${f.id}`, { active: false });
  }

  return {
    // ════════════════════════════════════════════════════════════════════
    0: {
      title: "A (Brazos Bend) sets up one field per record type, through Settings",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        state.A = state.A ?? {};
        for (const f of A_FIELDS) {
          const row = await addFieldViaSettings(p, { ...f, cell: ["A", f.entity] });
          if (f.required && row?.id && !row.is_required) await p.api("PATCH", `/settings/custom-fields/${row.id}`, { is_required: true });
          state.A[f.key] = row?.id;
          const placed = await placeViaSettings(p, f.label, f.placement, { shotStep: `placement_${f.key}` });
          const stored = (await listFields(p)).find((r) => r.id === row?.id);
          const want = Object.fromEntries(Object.entries(f.placement).filter(([, m]) => m !== "not_shown"));
          ok(`A: ${f.label}'s placement is stored as chosen`, JSON.stringify(Object.keys(stored?.placement ?? {}).sort()) === JSON.stringify(Object.keys(want).sort()),
            `${JSON.stringify(stored?.placement)} vs ${JSON.stringify(want)}`, ["A", f.entity, "set up"]);
          ok(`A: ${f.label}'s Placement names screens, never an id`, !/\b(S\d{1,3}|PORTAL_|REQUEST_|ROUTE_|AREA_|WORK_|READ_|UNIT_|PREMISE_)\w*/.test(placed.text), placed.text.slice(0, 200), ["A", f.entity, "set up"]);
        }
        const all = await listFields(p);
        const types = new Set(all.filter((r) => r.is_active).map((r) => r.data_type));
        ok("A: every field type is used at least once", ["text", "number", "date", "boolean", "select", "multi_select"].every((x) => types.has(x)), JSON.stringify([...types]));
        await p.goto(CF(A.t), { waitUntil: "networkidle" });
        await shot(p, "settings_table_A");
      },
    },
    1: {
      title: "the five Settings rules, in A",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        await settingsRules(p, "afill", { entity: "areas", firstLabel: "Warden", tidy: false });
        await viewWithoutInput(p, "a");
      },
    },
    2: {
      title: "C (SEU test) sets up the PO's 13 fields through Settings; 10th accepted, 11th refused",
      fn: async (ctx) => {
        const p = await page(ctx, C);
        state.C = state.C ?? {};
        for (const f of SEU_FIELDS) {
          const row = await addFieldViaSettings(p, { ...f, cell: ["SEU", f.label] });
          state.C[f.key] = row?.id;
          ok(`SEU: ${f.label} — key ${f.key}`, row?.key === f.key, row?.key, ["SEU", f.label, "set up"]);
          if (f.options) ok(`SEU: ${f.label} keeps its options in order, exact wording`, JSON.stringify(row?.options) === JSON.stringify(f.options), JSON.stringify(row?.options), ["SEU", f.label, "set up"]);
          ok(`SEU: ${f.label} help text kept`, (row?.help_text || null) === (f.help ?? null), String(row?.help_text), ["SEU", f.label, "set up"]);
          ok(`SEU: ${f.label} is not required`, row?.is_required === false, "", ["SEU", f.label, "set up"]);
          await placeViaSettings(p, f.label, f.placement, { shotStep: f.n === 1 || f.n === 13 ? `placement_${f.key}` : null });
          const stored = (await listFields(p)).find((r) => r.id === row?.id);
          ok(`SEU: ${f.label} placed on every screen the mapping names`, Object.keys(f.placement).every((k) => stored?.placement?.[k]), JSON.stringify(stored?.placement), ["SEU", f.label, "set up"]);
        }
        const prem = (await listFields(p)).filter((r) => r.entity === "premises" && r.is_active).length;
        ok("SEU: Premises holds 9 active", prem === 9, String(prem), ["rules", "seu-test · 10th accepted, 11th refused", "pass"]);
        await p.goto(CF(C.t), { waitUntil: "networkidle" });
        await shot(p, "settings_table_SEU");
        // the 10th accepted (through the screen), the 11th refused (through the screen)
        const tenth = await addFieldViaSettings(p, { entity: "premises", label: "SEU tenth probe", type: "text" });
        ok("SEU: a 10th Premises field is accepted", Boolean(tenth?.id), "", ["rules", "seu-test · 10th accepted, 11th refused", "pass"]);
        await p.goto(CF(C.t), { waitUntil: "networkidle" });
        await p.locator("button", { hasText: "+ Add custom field" }).first().click();
        await dialog(p).waitFor();
        await p.fill("#label", "SEU eleventh probe");
        await p.selectOption("#entity", { label: "Premises" });
        const ans = p.waitForResponse((r) => r.url().endsWith("/settings/custom-fields") && r.request().method() === "POST");
        await dialog(p).locator('button[data-variant="primary"]').last().click();
        const res = await ans;
        await p.waitForTimeout(600);
        const text = norm(await dialog(p).textContent().catch(() => ""));
        ok("SEU: an 11th Premises field is refused, and the dialog says why", res.status() === 422 && /10/.test(text), `${res.status()} ${text.slice(0, 300)}`, ["rules", "seu-test · 10th accepted, 11th refused", "pass"]);
        await shot(p, "seu_eleventh_refused");
        await dialog(p).getByRole("button", { name: "Cancel" }).click();
        await p.api("PATCH", `/settings/custom-fields/${tenth.id}`, { active: false });
      },
    },
    3: {
      title: "B (Pine Hill): its own roof_material (same key, other options), and the five rules in B",
      fn: async (ctx) => {
        const p = await page(ctx, B);
        state.B = state.B ?? {};
        // the same KEY as A's and C's, different options — B's own field.
        const roof = await addFieldViaSettings(p, { entity: "premises", label: "Roof Material", type: "select", options: ["Clay", "Thatch"] });
        state.B.roof_material = roof?.id;
        ok("B: its own roof_material exists with ITS options", roof?.key === "roof_material" && JSON.stringify(roof?.options) === '["Clay","Thatch"]', JSON.stringify(roof), ["iso", "premises", "same-name"]);
        await placeViaSettings(p, "Roof Material", { S16: "input", PREMISE_EDIT: "input", PREMISE_PAGE: "view", PORTAL_NEW_SERVICE: "input" });
        // B's area cap is B's: A still holds TEN active areas fields (phase 1
        // leaves them on), and B fills its own ten beside them.
        const pa = await page(ctx, A);
        const aAreas = (await listFields(pa)).filter((r) => r.entity === "areas" && r.is_active).length;
        ok("A holds 10 active Areas fields while B adds its own", aAreas === 10, String(aAreas), ["iso", "areas", "settings rules"]);
        await settingsRules(p, "bfill", { entity: "areas", firstLabel: "bfill filler 2" });
        const aAfter = (await listFields(pa)).filter((r) => r.entity === "areas" && r.is_active).length;
        ok("B switching its fields off left A's ten on", aAfter === 10, String(aAfter), ["iso", "areas", "settings rules"]);
        await tidyFillers(pa, "afill");
        await viewWithoutInput(p, "b");
        const aRoof = (await listFields(pa)).find((r) => r.key === "roof_material");
        ok("A: B's switching touched nothing of A's", aRoof?.is_active === true && JSON.stringify(aRoof.options) === '["Metal","Tile","Shingle"]', JSON.stringify(aRoof), ["iso", "premises", "same-name"]);
      },
    },
    ...more(H, { page, rowFor, fieldByKey }),
    ...accountPhases(H, { page }),
    ...opsPhases(H, { page }),
    ...requestPhases(H, { page }),
    ...isolationPhases(H, { page }),
    ...seuPhases(H, { page }),
  };
}

import { seuPhases } from "./cf_e2e_walk_seu.mjs";

import { isolationPhases } from "./cf_e2e_walk_isolation.mjs";

import { requestPhases } from "./cf_e2e_walk_requests.mjs";

import { opsPhases } from "./cf_e2e_walk_ops.mjs";

import { more } from "./cf_e2e_walk_more.mjs";
import { accountPhases } from "./cf_e2e_walk_accounts.mjs";
