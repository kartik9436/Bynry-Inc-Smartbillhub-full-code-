// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-WRK-4094 · Change: CR-073
// Rules:    BR-SHL-011 (unknown/invalid values fall back, never error)
// ───────────────────────────────────────────────────────

import { describe, expect, it } from "vitest";

import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig } from "@/components/tableTypes";

import { seedQueryFromUrl } from "./seedQueryFromUrl";

const config = {
  columns: [{ key: "name", label: "Name", sortable: true }],
  defaultSort: { sort: "name", dir: "asc" },
} as unknown as TableConfig<unknown>;

describe("DEF-WRK-4094 — a list screen seeds its search term from the URL", () => {
  it("takes `q` from the query string", () => {
    const state = seedQueryFromUrl(defaultRequestState(config), new URLSearchParams("q=MTR-W58"));
    expect(state.q).toBe("MTR-W58");
  });

  it("decodes what the popover encoded — a query is free text a person typed", () => {
    // `viewAllPath` builds this with encodeURIComponent; URLSearchParams decodes.
    const state = seedQueryFromUrl(
      defaultRequestState(config),
      new URLSearchParams("q=118%20Cedar%20%26%20Ridge"),
    );
    expect(state.q).toBe("118 Cedar & Ridge");
  });

  it("leaves the default alone when there is no `q`, and never throws", () => {
    expect(seedQueryFromUrl(defaultRequestState(config), new URLSearchParams("")).q).toBe("");
    expect(seedQueryFromUrl(defaultRequestState(config), new URLSearchParams("page=3")).q).toBe("");
    // An empty `q` is "show everything", not an error (BR-SHL-011).
    expect(seedQueryFromUrl(defaultRequestState(config), new URLSearchParams("q=")).q).toBe("");
  });

  it("reads ONLY `q` — the four Work lists never write the URL back", () => {
    // Reading a page/sort they will never write would restore, on reload, a
    // state the user had since left. See the helper's docstring.
    const state = seedQueryFromUrl(
      defaultRequestState(config),
      new URLSearchParams("q=x&page=7&per=100&sort=nonsense&dir=desc"),
    );
    expect(state.page).toBe(1);
    expect(state.sort).toBe("name");
    expect(state.dir).toBe("asc");
  });
});
