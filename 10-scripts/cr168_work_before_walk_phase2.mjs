// CR-168-BRC10 round 1 — phase 2 of `cr168_work_before_walk.mjs`: the states
// that need a press. Writes only what a clerk's presses write: one Reschedule
// attempt with typed garbage, one edit save, one raise attempt, one office
// "Mark complete" (to reach the Approvals state and reproduce ruling 18), one
// accept through the API (to reproduce beta #10), one empty Add part press,
// one template drafted through the builder.
export default async function phase2(w) {
  const { page, BASE, TENANT, say, settle, shot, mainText, dialogText, api, dump, visit, step, ctx } = w;
  const T = (p) => `${BASE}/${TENANT}${p}`;
  const go = async (p) => { await page.goto(T(p), { waitUntil: "networkidle", timeout: 30000 }).catch(() => say("goto timeout", p)); await settle(1500); };
  const click = async (re, opts = {}) => { const b = page.getByRole(opts.role ?? "button", { name: re }); await b.first().click({ timeout: 5000 }); await settle(900); };
  const toastText = async () => (await page.locator('[role="status"], [role="alert"], [data-toast]').allInnerTexts().catch(() => [])).join(" | ");
  const byNo = (no) => ctx.rows.find((r) => (r.order_no ?? r.number) === no);

  // ── 1·1 the list: bulk, reschedule garbage (beta #11), filter (beta #12), search clears (beta #3)
  await step("bulk-assign", async () => {
    await go("/work/orders");
    const boxes = page.locator('main tbody input[type="checkbox"]');
    await boxes.nth(2).check(); await boxes.nth(3).check(); await settle();
    await shot("b02a-bulk-bar", "1·1 two orders ticked — the bulk bar");
    await click(/^Assign selected/);
    await shot("a02-bulk-assign", "1·1b Assign selected… dialog");
    say(await dialogText()); await dump("a02-dialog", '[role="dialog"]');
    await page.keyboard.press("Escape"); await settle();
  });
  await step("bulk-reschedule-garbage", async () => {
    await click(/^Reschedule selected/);
    const inputs = page.locator('[role="dialog"] input');
    say("RESCHEDULE INPUT TYPES:", JSON.stringify(await inputs.evaluateAll((els) => els.map((e) => e.type))));
    const n = await inputs.count();
    for (let i = 0; i < n; i++) { await inputs.nth(i).fill(i === 0 ? "UU898" : "99989").catch((e) => say("fill refused", i, String(e).split("\n")[0])); }
    await shot("b11-reschedule-garbage", "beta #11 — typed UU898 / 99989 into the reschedule fields");
    await dump("b11-dialog", '[role="dialog"]');
    await page.getByRole("button", { name: /^Reschedule$/ }).first().click().catch(() => {});
    await settle(2000);
    await shot("b11b-reschedule-after-press", "beta #11/#4 — after pressing Reschedule with garbage");
    say("TOAST:", await toastText()); say(await dialogText());
    await page.keyboard.press("Escape"); await settle();
  });
  await step("filter-menu", async () => {
    await go("/work/orders");
    await click(/Filter/);
    await shot("b12-filter-menu", "beta #12 — + Filter opened");
    say(await mainText().then((s) => s.slice(0, 1500)));
    await page.keyboard.press("Escape");
  });
  await step("search-clear", async () => {
    await go("/work/orders");
    const s = page.locator('main input[type="search"], main input[placeholder^="Search"]').first();
    say("SEARCH INPUT TYPE:", await s.getAttribute("type"));
    await s.fill("WO-0016"); await settle(1500);
    const box = await s.boundingBox();
    await page.screenshot({ path: `${w.OUT}/b03-search-clear.png`, clip: { x: box.x - 10, y: box.y - 10, width: box.width + 20, height: box.height + 20 } });
    await shot("b03b-search-result", "beta #3 — search typed; two clear controls?");
  });

  // ── 1·2 a not-completed order (WO-0037, scheduled, D. Ortiz)
  const o37 = byNo("WO-0037");
  if (o37) {
    for (const tab of ["overview", "checklist", "parts", "location", "customer", "audit"]) {
      await step(`o37-${tab}`, () => visit(`/work/orders/${o37.id}?tab=${tab}`, `a03-order-${tab}`, `1·2 WO-0037 ?tab=${tab}`));
    }
    await step("o37-cancel-dialog", async () => {
      await go(`/work/orders/${o37.id}?tab=overview`);
      await click(/^Cancel order/);
      await shot("a11-cancel-dialog", "1·2g Cancel order dialog");
      say(await dialogText()); await dump("a11-dialog", '[role="dialog"]');
      await page.keyboard.press("Escape"); await settle();
    });
    await step("o37-edit", () => visit(`/work/orders/${o37.id}/edit`, "a13-edit-assigned", "1·3b edit page on an assigned order (Reassign)"));
  }
  const o16 = byNo("WO-0016");
  if (o16) {
    await step("o16-edit", () => visit(`/work/orders/${o16.id}/edit`, "a12-edit-unassigned", "1·3a edit page on an unassigned order (Assign)"));
    await step("o16-candidates", async () => { const c = await api("GET", `work-orders/${o16.id}/candidates`); say("CANDIDATES WO-0016:", c.status, JSON.stringify(c.data).slice(0, 1500)); });
    await step("o16-save-refused", async () => {
      // beta #4: a save the server refuses. Pick the first technician offered
      // in the assignee select whatever their skill, and press save.
      const sel = page.locator("main select");
      const n = await sel.count();
      for (let i = 0; i < n; i++) {
        const opts = await sel.nth(i).evaluate((e) => Array.from(e.options).map((o) => [o.value, o.textContent.trim()]));
        say("EDIT SELECT", i, JSON.stringify(opts).slice(0, 400));
      }
      const pc = page.locator("main select").filter({ hasText: /Ortiz|Patel|Chen|Okoro/ });
      if (await pc.count()) {
        const opts = await pc.first().evaluate((e) => Array.from(e.options).map((o) => o.value).filter(Boolean));
        await pc.first().selectOption(opts[opts.length - 1]);
      }
      const datei = page.locator('main input[type="date"], main input[name*="due" i]');
      say("EDIT DATE INPUT TYPES:", JSON.stringify(await page.locator("main input").evaluateAll((els) => els.map((e) => [e.type, e.name || e.id]))));
      await shot("b04a-edit-before-save", "beta #4 — edit with a change, before Save");
      const reqs = [];
      const h = (r) => { if (r.url().includes("/work-orders/")) reqs.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`); };
      page.on("response", h);
      await page.getByRole("button", { name: /^(Save|Assign|Reassign)/ }).first().click().catch((e) => say("no save", String(e).split("\n")[0]));
      await settle(2500);
      page.off("response", h);
      say("EDIT SAVE RESPONSES:", JSON.stringify(reqs));
      await shot("b04b-edit-after-save", "beta #4 — after Save");
      say("TOAST:", await toastText()); say((await mainText()).slice(0, 800));
    });
  }

  // ── 1·4 the raise wizard (beta #14, #16, #32)
  await step("raise", async () => {
    await go("/work/orders/new");
    await dump("a14-raise-step1");
    const sels = page.locator("main select");
    for (let i = 0; i < (await sels.count()); i++) say("RAISE SELECT", i, JSON.stringify(await sels.nth(i).evaluate((e) => Array.from(e.options).map((o) => o.textContent.trim()))).slice(0, 1500));
    await page.getByRole("button", { name: /^Continue/ }).first().click(); await settle();
    await shot("b16a-raise-continue-empty", "beta #16 — Continue with nothing filled");
    say("TOAST:", await toastText()); say((await mainText()).slice(0, 600));
  });

  // ── the doors: account (beta #22) and asset (beta #23)
  await step("account-door", async () => {
    const a = await api("GET", "accounts?per=3"); const acc = (a.data?.results ?? [])[0];
    say("ACCOUNT:", acc?.id, acc?.account_no ?? acc?.number);
    if (acc) {
      await go(`/accounts/${acc.id}`);
      await shot("b22a-account-page", "beta #22 — an account page: is there a Raise work order?");
      say("ACCOUNT BUTTONS:", JSON.stringify(await w.buttons()).slice(0, 2000));
      await go(`/accounts/${acc.id}/work-orders/new`);
      await shot("a19-account-raise", "1·4e — /accounts/:id/work-orders/new");
      say((await mainText()).slice(0, 400));
    }
  });
  await step("asset-door", async () => {
    const a = await api("GET", "assets?per=3"); const as = (a.data?.results ?? [])[0];
    say("ASSET:", as?.id, as?.asset_no ?? as?.number);
    if (as) {
      await go(`/assets/${as.id}`);
      await shot("b23a-asset-page", "beta #23 — an asset page: Raise work order?");
      say("ASSET BUTTONS:", JSON.stringify(await w.buttons()).slice(0, 1500));
      await visit(`/assets/${as.id}/work-orders/new`, "a20-asset-raise", "1·4f — the asset door as it is");
    }
  });

  // ── the map pin (beta #19)
  await step("map-pin", async () => {
    await go("/work/map");
    await page.getByRole("button", { name: /^WO-00/ }).first().click(); await settle(1500);
    await shot("b19-map-pin-click", "beta #19 — a pin clicked");
    say("URL AFTER PIN:", page.url().replace(BASE, "")); say((await mainText()).slice(0, 600));
  });

  // ── parts (beta #24, #25, #26, ruling 29/32)
  await step("parts-add", async () => {
    await go("/work/parts");
    await click(/Add part/);
    await shot("a36-add-part", "5·1a Add a part as it is");
    say(await dialogText()); await dump("a36-dialog", '[role="dialog"]');
    await page.locator('[role="dialog"]').getByRole("button", { name: /^Add part/ }).click().catch(() => {});
    await settle();
    await shot("a37-add-part-empty", "5·1b Add part pressed empty");
    say(await dialogText());
    await page.keyboard.press("Escape");
  });

  // ── rules: search (beta #15), builder steps, row actions (beta #5)
  await step("rules-search", async () => {
    await go("/work/rules");
    const s = page.locator('main input[type="search"], main input[placeholder*="earch"]').first();
    await s.fill("Leak"); await settle(1500);
    await shot("b15-rules-search", "beta #15 — rules search typed 'Leak'");
    say((await mainText()).slice(0, 1500));
  });
  await step("rule-builder", async () => {
    await go("/work/rules/new");
    for (let i = 1; i <= 5; i++) {
      await shot(`a57-rule-step${i}`, `7·2 rule builder step ${i}`);
      say((await mainText()).slice(0, 800)); await dump(`a57-rule-step${i}`);
      if (i === 1) {
        await page.locator("main input").first().fill("Walk rule").catch(() => {});
        const sels = page.locator("main select");
        for (let k = 0; k < (await sels.count()); k++) {
          const opts = await sels.nth(k).evaluate((e) => Array.from(e.options).map((o) => o.value).filter(Boolean));
          if (opts.length) await sels.nth(k).selectOption(opts[0]);
        }
      }
      await page.getByRole("button", { name: /^Next/ }).first().click().catch(() => {}); await settle();
    }
  });

  // ── templates: builder walked with the Meter exchange pack (beta #6, #7, #8, ruling 5–7, 9)
  await step("template-builder", async () => {
    await go("/work/templates/new");
    await page.getByRole("button", { name: /^Meter exchange/ }).first().click().catch(() => {}); await settle();
    await page.locator("main input").first().fill("Walk template — CR-168");
    const sels = page.locator("main select");
    const svc = await sels.first().evaluate((e) => Array.from(e.options).map((o) => [o.value, o.textContent.trim()]));
    say("SERVICE OPTIONS:", JSON.stringify(svc));
    const water = svc.find(([, l]) => /water/i.test(l)); if (water) await sels.first().selectOption(water[0]);
    await shot("a48-builder-details-filled", "6·3a Details filled from the pack");
    await dump("a48-builder-details");
    const names = ["a48b-details", "a49-safety", "a50-tasks", "a51-materials", "a52-readings", "a53-help", "a54-signature", "a55-review"];
    for (let i = 1; i < names.length; i++) {
      await page.getByRole("button", { name: /^Continue/ }).first().click().catch(() => {}); await settle(1200);
      await shot(names[i], `6·3 builder step ${i + 1}`);
      say((await mainText()).slice(0, 1800)); await dump(names[i]);
    }
  });

  // ── ruling 18 and beta #10 #18: the office marks a job complete, then approvals
  if (o37) {
    await step("mark-complete", async () => {
      await go(`/work/orders/${o37.id}?tab=overview`);
      await shot("b18a-order-head-mark-complete", "ruling 18 — Mark complete on the office's order page");
      await click(/^Mark complete/);
      await settle(2000);
      say("TOAST:", await toastText());
      await shot("b18b-after-mark-complete", "ruling 18 — after the office pressed Mark complete");
      say((await mainText()).slice(0, 800));
      await visit("/work/awaiting-approval", "a21b-approvals-one-row", "2·1 Approvals with the office-completed row");
      const eye = page.locator("main tbody a").first();
      say("APPROVALS ROW LINK HREF:", await eye.getAttribute("href").catch(() => null));
      await eye.click().catch(() => {}); await settle(2000);
      say("URL AFTER EYE:", page.url().replace(BASE, ""));
      await shot("b18c-approvals-eye-destination", "beta #18 — where the approvals row's eye goes");
    });
    await step("accept-then-find", async () => {
      const r = await api("POST", `work-orders/${o37.id}/accept`, {});
      say("ACCEPT:", r.status, JSON.stringify(r.data).slice(0, 600));
      const l = await api("GET", "work-orders?per=100&q=WO-0037");
      say("LIST AFTER ACCEPT q=WO-0037:", l.status, JSON.stringify((l.data?.results ?? []).map((x) => x.order_no)));
      await go("/work/orders");
      const s = page.locator('main input[type="search"], main input[placeholder^="Search"]').first();
      await s.fill("WO-0037"); await settle(1500);
      await shot("b10-accepted-order-not-found", "beta #10 — the accepted order searched on Orders");
      say((await mainText()).slice(0, 1200));
    });
  }
}
