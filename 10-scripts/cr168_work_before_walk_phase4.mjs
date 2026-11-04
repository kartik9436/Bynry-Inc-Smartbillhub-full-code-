// CR-168-BRC10 round 1 — phase 4: the account's Work tab (beta #22), the
// list's + Filter (beta #12), and Put on hold… pressed on WO-0029 (1·2f) —
// which writes one hold, the only write here.
export default async function phase4(w) {
  const { page, BASE, TENANT, say, settle, shot, mainText, dialogText, api, dump, step, ctx } = w;
  const T = (p) => `${BASE}/${TENANT}${p}`;
  const go = async (p) => { await page.goto(T(p), { waitUntil: "networkidle", timeout: 30000 }).catch(() => say("goto timeout", p)); await settle(1500); };
  const toastText = async () => (await page.locator('[role="status"], [role="alert"], [data-toast], [data-sonner-toast]').allInnerTexts().catch(() => [])).join(" | ");
  await step("account-work-tab", async () => {
    const a = await api("GET", "accounts?per=3"); const acc = (a.data?.results ?? [])[0];
    await go(`/accounts/${acc.id}?tab=work`);
    await shot("b22b-account-work-tab", "beta #22 — the account's Work tab");
    say((await mainText()).slice(0, 1500));
    say("RAISE-LIKE:", JSON.stringify((await w.buttons()).filter((b) => /raise|work order|new order/i.test(b))));
  });
  await step("filter", async () => {
    await go("/work/orders");
    const f = page.getByText(/\+ ?Filter/).first();
    say("FILTER TAG:", await f.evaluate((e) => `${e.tagName} ${e.getAttribute("role")} ${e.outerHTML.slice(0, 200)}`));
    await f.click({ timeout: 5000 }); await settle();
    await shot("b12-filter-menu", "beta #12 — + Filter opened");
    say((await page.locator("body").innerText()).slice(0, 2500));
  });
  await step("hold", async () => {
    const o = ctx.rows.find((r) => (r.order_no ?? r.number) === "WO-0029");
    await go(`/work/orders/${o.id}?tab=overview`);
    let sent = null;
    page.on("request", (r) => { if (r.url().includes("/hold")) sent = `${r.method()} ${r.postData()}`; });
    await page.getByRole("button", { name: /^Put on hold/ }).first().click(); await settle(2000);
    say("HOLD REQUEST:", sent, "DIALOG:", await dialogText(), "TOAST:", await toastText());
    await shot("a10-put-on-hold", "1·2f Put on hold… pressed");
    say((await mainText()).slice(0, 500));
  });
}
