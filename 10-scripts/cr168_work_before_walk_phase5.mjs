// CR-168-BRC10 round 1 — phase 5: the two flows that need real input to get
// past step 1 — the New work order wizard (steps 2, 3 and what follows the
// press: 1·4b–1·4d) raised with a real premises id, and Import parts run end
// to end with 08-qa/work-2026-10-04/parts-import-walk.csv (5·2a–5·2e).
// Writes: one work order and up to three parts, exactly as a clerk would.
export default async function phase5(w) {
  const { page, BASE, TENANT, say, settle, shot, mainText, api, dump, step } = w;
  const T = (p) => `${BASE}/${TENANT}${p}`;
  const go = async (p) => { await page.goto(T(p), { waitUntil: "networkidle", timeout: 30000 }).catch(() => say("goto timeout", p)); await settle(1500); };
  if (process.env.SKIP_RAISE !== "1") await step("raise-wizard", async () => {
    const pr = await api("GET", "premises?per=5&q=240%20Sable");
    const prem = (pr.data?.results ?? [])[0];
    say("PREMISES:", prem?.id, prem?.address_line1 ?? prem?.name);
    await go("/work/orders/new");
    const inputs = page.locator("main input");
    await inputs.nth(0).fill(prem.id);
    await inputs.nth(1).fill("Meter Change");
    await page.locator("main select").first().selectOption({ index: 3 });
    await page.getByRole("button", { name: /^Continue/ }).click(); await settle(1200);
    await shot("a16-raise-step2", "1·4b raise step 2 as it is");
    say((await mainText()).slice(0, 800)); await dump("a16-raise-step2");
    await page.getByRole("button", { name: /^Continue/ }).click(); await settle(1200);
    await shot("a17-raise-step3", "1·4c raise step 3 as it is");
    say((await mainText()).slice(0, 800)); await dump("a17-raise-step3");
    await page.getByRole("button", { name: /^Raise work order/ }).click(); await settle(2500);
    await shot("a18-raise-after-press", "1·4d what follows the press today");
    say("URL AFTER RAISE:", page.url().replace(BASE, ""));
    say((await mainText()).slice(0, 600));
  });
  await step("import-parts", async () => {
    await go("/work/parts/import");
    const file = page.locator('input[type="file"]');
    await file.setInputFiles(new URL("../08-qa/work-2026-10-04/parts-import-walk.csv", import.meta.url).pathname);
    await settle(1500);
    const stages = [["a39-import-transform", /^Transform/], ["a40-import-validate", /^Validate/], ["a41-import-load", /^Load/]];
    for (const [name, re] of stages) {
      await page.getByRole("button", { name: re }).last().click().catch((e) => say("stage", String(e).split("\n")[0]));
      await settle(2500);
      await shot(name, `5·2 ${name}`);
      say((await mainText()).slice(0, 2000)); await dump(name);
    }
    // The approval tick is a styled checkbox; press its words.
    await page.getByText("I approve this load.").click().catch((e) => say("approve", String(e).split("\n")[0]));
    await settle(800);
    await page.getByRole("button", { name: /^Commit load/ }).click().catch((e) => say("commit", String(e).split("\n")[0]));
    await settle(4000);
    await shot("a42-import-result", "5·2e Result");
    say((await mainText()).slice(0, 2500));
  });
}
