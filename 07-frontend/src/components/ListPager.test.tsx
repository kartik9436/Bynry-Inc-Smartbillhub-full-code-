// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3 — B14 rule 16 for the five list tables that are not
//          the shared DataTable (DEF-223).
// Rules:   B14 rule 16 (the footer's exact grammar and its five page sizes)
// ───────────────────────────────────────────────────────
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ListPager, pageSlice } from "./ListPager";

describe("ListPager — B14 rule 16's footer, for a client-held list", () => {
  function render(total: number, page = 1): string {
    return renderToStaticMarkup(
      <ListPager
        total={total}
        page={page}
        per={50}
        onPage={() => undefined}
        onPer={() => undefined}
      />,
    );
  }

  it("carries the range, the five page sizes and both arrows", () => {
    const html = render(320);
    expect(html).toContain(i18n.t("table.pager.pageSize"));
    for (const size of [50, 100, 200, 500, 1000]) {
      expect(html).toContain(`>${size}<`);
    }
    expect(html).toContain(i18n.t("table.pager.prev"));
    expect(html).toContain(i18n.t("table.pager.next"));
  });

  it("an EMPTY list reads 0–0 of 0 — the first row of nothing is not row 1", () => {
    expect(render(0)).toContain(i18n.t("table.pager.range", { from: 0, to: 0, total: 0 }));
  });

  it("the footer's numbers and the rows it sits under come from ONE slice", () => {
    const rows = Array.from({ length: 320 }, (_, index) => index);
    expect(pageSlice(rows, 1, 50)).toHaveLength(50);
    expect(pageSlice(rows, 2, 50)[0]).toBe(50);
    expect(pageSlice(rows, 7, 50)).toEqual([300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319]);
    // …and the range the footer prints for that same page.
    expect(render(320, 7)).toContain(
      i18n.t("table.pager.range", { from: 301, to: 320, total: 320 }),
    );
  });

  it("the arrows disable at the ends rather than vanishing", () => {
    expect(render(320, 1)).toContain("disabled");
    expect(render(320, 7)).toContain("disabled");
  });
});
