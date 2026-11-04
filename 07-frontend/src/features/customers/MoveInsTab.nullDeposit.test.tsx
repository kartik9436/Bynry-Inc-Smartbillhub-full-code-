// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9758 — the Move-ins tab crashed the whole screen
//          ("Cannot read properties of null (reading 'recorded')") on app-dev
//          2.531.2 as soon as the list held a request row: the server serves
//          `deposit: null` on a request (a request holds no deposit) and the
//          deposit column dereferenced it. One bad row took down every row.
// ───────────────────────────────────────────────────────
//
// Both deposit renderers must draw `—` for a row with no deposit, never throw:
// the list's own cell (`MoveInDepositCell`, mounted since 2.536.0) and the
// older `MoveDepositCellView` (still exported, the one app-dev mounts).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { MoveInDepositCell } from "./MoveInsTab";

const text = (html: string) => html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();

describe("DEF-CUS-9758 — a request row's null deposit draws a dash", () => {
  it("the list's deposit cell draws — for null", () => {
    expect(text(renderToStaticMarkup(<MoveInDepositCell deposit={null} />))).toBe("—");
  });

});
