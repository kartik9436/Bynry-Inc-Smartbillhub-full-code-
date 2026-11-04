// CR-168-BRC10 round 1 — phase 1 of `cr168_work_before_walk.mjs`: every Work
// back-office address opened as it stands, photographed and inventoried.
// Reads only; writes nothing.
export default async function phase1(w) {
  const { visit, step, ctx, page, BASE, TENANT, shot, say, mainText, dump } = w;
  await step("list", () => visit("/work/orders", "a01-orders-list", "1·1 Orders as it opens"));
  await step("approvals", () => visit("/work/awaiting-approval", "a21-approvals", "2·1 Approvals tab"));
  await step("map", () => visit("/work/map", "a24-map", "3·1 Map"));
  await step("crews", () => visit("/work/crews", "a25-crews", "4·1 Crews"));
  const slug = "d-ortiz";
  if (slug) {
    for (const tab of ["overview", "jobs", "certifications", "performance"]) {
      await step(`tech-${tab}`, () => visit(`/work/crews/${slug}?tab=${tab}`, `a31-tech-${tab}`, `4·2 technician ${slug} ?tab=${tab}`));
    }
  }
  await step("parts", () => visit("/work/parts", "a35-parts", "5·1 Parts"));
  await step("parts-import", () => visit("/work/parts/import", "a38-parts-import", "5·2a Import parts"));
  await step("templates", () => visit("/work/templates", "a43-templates", "6·1 Templates"));
  const tpl = ctx.tplrows.find((t) => /exchange/i.test(t.name)) ?? ctx.tplrows[0];
  if (tpl) {
    for (const tab of ["overview", "usage", "versions", "audit"]) {
      await step(`tpl-${tab}`, () => visit(`/work/templates/${tpl.id}?tab=${tab}`, `a44-template-${tab}`, `6·2 template ${tpl.name} ?tab=${tab}`));
    }
  }
  await step("builder", () => visit("/work/templates/new", "a48-builder-1", "6·3a builder step 1"));
  await step("rules", () => visit("/work/rules", "a56-rules", "7·1 Rules"));
  await step("rule-new", () => visit("/work/rules/new", "a57-rule-new-1", "7·2a rule builder step 1"));
  const rule = ctx.rrows[0];
  if (rule) await step("rule-detail", () => visit(`/work/rules/${rule.id}`, "a62-rule-detail", "7·3a a rule's own page (does it exist?)"));
  await step("performance", () => visit("/work/performance", "a65-performance", "8·1 Performance"));
  await step("new-order", () => visit("/work/orders/new", "a14-raise-1", "1·4a raise step 1"));
}
