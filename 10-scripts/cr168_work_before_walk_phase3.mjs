// CR-168-BRC10 round 1 — phase 3 of `cr168_work_before_walk.mjs`: what phase 2
// could not reach. Writes: one edit save per assignee kind (to read the
// server's refusal), the office ticking WO-0037's checklist and pressing Mark
// complete (ruling 18), one temp password for a technician and that
// technician's own password change (beta #33).
export default async function phase3(w) {
  const { page, BASE, TENANT, say, settle, shot, mainText, dialogText, api, dump, visit, step, ctx } = w;
  const T = (p) => `${BASE}/${TENANT}${p}`;
  const go = async (p) => { await page.goto(T(p), { waitUntil: "networkidle", timeout: 30000 }).catch(() => say("goto timeout", p)); await settle(1500); };
  const byNo = (no) => ctx.rows.find((r) => (r.order_no ?? r.number) === no);
  const toastText = async () => (await page.locator('[role="status"], [role="alert"], [data-toast], [data-sonner-toast]').allInnerTexts().catch(() => [])).join(" | ");

  // beta #4: what the edit save sends and what comes back, per assignee kind.
  const o18 = byNo("WO-0018");
  if (o18) {
    for (const who of ["D. Ortiz", "Field crew A (2)", "Redline Meter Services"]) {
      await step(`edit-save-${who}`, async () => {
        await go(`/work/orders/${o18.id}/edit`);
        const sel = page.locator("main select").nth(2);
        await sel.selectOption({ label: who }).catch((e) => say("no option", who, String(e).split("\n")[0]));
        let body = null; let resp = null;
        const h = async (r) => { if (r.request().method() === "PATCH") { body = r.request().postData(); resp = `${r.status()} ${await r.text().catch(() => "")}`; } };
        page.on("response", h);
        await page.getByRole("button", { name: /^(Save|Assign|Reassign)/ }).first().click().catch((e) => say("no save btn", String(e).split("\n")[0]));
        await settle(2500); page.off("response", h);
        say(`EDIT SAVE as ${who}: sent ${body} → ${resp}`);
        say("TOAST:", await toastText(), "URL:", page.url().replace(BASE, ""));
        await shot(`b04-edit-save-${who.replace(/[^A-Za-z]+/g, "-")}`, `beta #4 — edit saved with ${who}`);
      });
    }
  }
  await step("filter-menu", async () => {
    await go("/work/orders");
    say("FILTER-LIKE BUTTONS:", JSON.stringify((await w.buttons()).filter((b) => /filter/i.test(b))));
    await page.locator("main button", { hasText: "Filter" }).first().click();
    await settle();
    await shot("b12-filter-menu", "beta #12 — + Filter opened");
    say((await page.locator("body").innerText()).match(/Filter[\s\S]{0,600}/)?.[0]);
    // pick priority if offered
    await page.getByText(/^Priority$/).first().click().catch(() => {});
    await settle();
    await shot("b12b-filter-priority", "beta #12 — the Priority filter");
    say((await page.locator("body").innerText()).slice(0, 2500));
  });
  await step("map-pin", async () => {
    await go("/work/map");
    const pin = page.getByRole("button", { name: /^WO-00/ }).first();
    await pin.click({ force: true, timeout: 5000 }).catch((e) => say("pin click", String(e).split("\n")[0]));
    await settle(1500);
    await shot("b19-map-pin-click", "beta #19 — a pin clicked");
    say("URL AFTER PIN:", page.url().replace(BASE, "")); say((await mainText()).slice(0, 800));
  });
  const o37 = byNo("WO-0037");
  if (o37) {
    await step("office-ticks-and-completes", async () => {
      await go(`/work/orders/${o37.id}?tab=checklist`);
      const boxes = page.locator('main input[type="checkbox"]');
      for (let round = 0; round < 3; round++) {
        const n = await boxes.count();
        for (let i = 0; i < n; i++) { const b = boxes.nth(i); if (!(await b.isChecked().catch(() => true)) && (await b.isEnabled().catch(() => false))) { await b.check().catch(() => {}); await settle(700); } }
      }
      await shot("b18a-office-ticked-checklist", "ruling 18 — the office ticked the checklist itself");
      say((await mainText()).slice(0, 1500));
      const mc = page.getByRole("button", { name: /^Mark complete/ });
      say("MARK COMPLETE ENABLED:", await mc.isEnabled().catch(() => "n/a"));
      await mc.click({ timeout: 5000 }).catch((e) => say("mark complete", String(e).split("\n")[0]));
      await settle(2500);
      say("TOAST:", await toastText());
      await shot("b18b-after-mark-complete", "ruling 18 — after the office pressed Mark complete");
      say((await mainText()).slice(0, 800));
    });
    await step("approvals-row", async () => {
      await visit("/work/awaiting-approval", "a21b-approvals-one-row", "2·1 Approvals with an office-completed row");
      const eye = page.locator("main tbody a").first();
      say("APPROVALS ROW LINK HREF:", await eye.getAttribute("href").catch(() => null));
      await eye.click({ timeout: 5000 }).catch((e) => say("eye", String(e).split("\n")[0])); await settle(2000);
      say("URL AFTER EYE:", page.url().replace(BASE, ""));
      await shot("b18c-approvals-eye-destination", "beta #18 — where the approvals row's eye goes");
      say((await mainText()).slice(0, 1500));
      say("BUTTONS THERE:", JSON.stringify(await w.buttons()).slice(0, 1500));
    });
    await step("order-completed-shape", async () => {
      for (const tab of ["overview", "checklist"]) await visit(`/work/orders/${o37.id}?tab=${tab}`, `a04-order-completed-${tab}`, `1·2a′/b′ WO-0037 after completion ?tab=${tab}`);
    });
    await step("accept-then-find", async () => {
      const r = await api("POST", `work-orders/${o37.id}/accept`, {});
      say("ACCEPT:", r.status, JSON.stringify(r.data).slice(0, 500));
      const l = await api("GET", "work-orders?per=100&q=WO-0037");
      say("ORDERS LIST q=WO-0037 AFTER ACCEPT:", l.status, JSON.stringify((l.data?.results ?? []).map((x) => x.order_no ?? x.number)));
      const a = await api("GET", "work-orders/awaiting-approval?per=100");
      say("AWAITING AFTER ACCEPT:", JSON.stringify((a.data?.results ?? []).map((x) => x.order_no ?? x.number)));
      await go("/work/orders");
      const s = page.locator('main input[type="search"]').first();
      await s.fill("WO-0037"); await settle(1500);
      await shot("b10-accepted-order-searched", "beta #10 — the accepted order searched on Orders");
      say((await mainText()).slice(0, 1000));
      await go(`/work/orders/${o37.id}`);
      await shot("b10b-accepted-order-direct", "beta #10 — the accepted order opened by its address");
      say((await mainText()).slice(0, 600));
    });
  }
  await step("technician-invite-password", async () => {
    const users = await api("GET", "users?per=100");
    const tech = (users.data?.results ?? users.data ?? []).find((u) => u.role_code === "field_technician" || /technician/i.test(u.role ?? ""));
    say("TECH USER:", JSON.stringify(tech).slice(0, 300));
    if (!tech) return;
    const tp = await api("POST", `users/${tech.id ?? tech.user_id}/temp-password`, {});
    say("TEMP PASSWORD:", tp.status, tp.data?.temp_password ? "(issued)" : JSON.stringify(tp.data).slice(0, 300));
    if (!tp.data?.temp_password) return;
    const ctx2 = await page.context().browser().newContext({ viewport: { width: 1440, height: 1000 } });
    const p2 = await ctx2.newPage();
    await p2.goto(T("/signin"), { waitUntil: "networkidle" });
    await p2.fill("#signin-email", tech.email);
    await p2.fill("#signin-password", tp.data.temp_password);
    await p2.click('button[type="submit"]');
    await p2.waitForTimeout(3000);
    await p2.screenshot({ path: `${w.OUT}/b33a-technician-first-signin.png`, fullPage: true });
    say("\n=== b33a-technician-first-signin.png — URL", p2.url().replace(BASE, ""));
    say((await p2.locator("body").innerText()).slice(0, 800));
    const pw = p2.locator('input[type="password"]');
    const n = await pw.count();
    say("PASSWORD INPUTS:", n);
    if (n >= 2) {
      if (n === 3) { await pw.nth(0).fill(tp.data.temp_password); await pw.nth(1).fill("N3w!Technician#2026"); await pw.nth(2).fill("N3w!Technician#2026"); }
      else { await pw.nth(0).fill("N3w!Technician#2026"); await pw.nth(1).fill("N3w!Technician#2026"); }
      const resp = [];
      p2.on("response", async (r) => { if (r.url().includes("/api/")) resp.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`); });
      await p2.locator('button[type="submit"]').first().click().catch(() => {});
      await p2.waitForTimeout(3000);
      say("PASSWORD CHANGE RESPONSES:", JSON.stringify(resp));
      await p2.screenshot({ path: `${w.OUT}/b33b-technician-set-password.png`, fullPage: true });
      say("\n=== b33b-technician-set-password.png — URL", p2.url().replace(BASE, ""));
      say((await p2.locator("body").innerText()).slice(0, 800));
    }
    await ctx2.close();
  });
}
