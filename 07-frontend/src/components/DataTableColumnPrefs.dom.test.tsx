// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-007 TC-3/TC-4/TC-7 · US-SHL-013 (the preference service)
// Defect:   DEF-647 — "the column selector never saves"
// Rules:    BR-SHL-013 (column prefs per user+tenant+screen; identity column
//           unhideable) · BR-SHL-024 (unknown key = absent → defaults) ·
//           BR-SHL-027 (SERVER-SIDE always, never localStorage-only)
// ───────────────────────────────────────────────────────
// ⚠ **THIS SUITE EXISTS BECAUSE A SAME-RENDER ASSERTION PASSES ON THE BUG.**
// `DataTable.test.tsx` proved `toggleColumnVisible` returns the right ordered
// array, and proved the header re-renders from it. Both were green on the
// shipped tree, and the product still forgot the user's columns the moment the
// component remounted — because nothing ever asked where that array went.
//
// So every test below UNMOUNTS AND REMOUNTS. That is the whole point: a
// preference is a claim about the NEXT mount, and only a second mount can
// falsify it. `DataTable.test.tsx:466` was an `it.todo` whose own title said it
// "lands with US-SHL-013's service" — this is that test, and it lives in a
// `.dom.test.tsx` file because remounting needs a real DOM and
// `vitest.config.ts` reserves the default `node` environment for the 200+
// static-markup suites (DEF-523).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DataTable } from "./DataTable";
import { defaultRequestState } from "./tableTypes";
import type { TableConfig } from "./tableTypes";

// ── The stand-in for `user_preferences` ────────────────────────────────────
// Keyed by (tenant, user, key), exactly as the table's `uq_user_prefs` unique
// constraint is, so "another user sees their own default" is a property of the
// STORE here and not of a stub that happens to answer null. The real scoping is
// the server's (`tests/test_us_shl_013_user_preferences.py` proves both halves,
// the tenant one under a non-superuser RLS probe); what this fake reproduces is
// the shape a correctly-scoped server presents to the client.
const rows = new Map<string, unknown>();
let session = { tenant: "silvercreek", user: "alex" };
const seen: string[] = []; // every key the component asked for, in order

function slot(key: string): string {
  return `${session.tenant}|${session.user}|${key}`;
}

vi.mock("@/api/endpoints", () => ({
  getUserPreference: (key: string) => {
    seen.push(`GET ${key}`);
    // BR-SHL-024: an unknown key reads as ABSENT — the endpoint answers 200
    // with `value: null`, which the wrapper hands back as null.
    return Promise.resolve(rows.has(slot(key)) ? rows.get(slot(key)) : null);
  },
  putUserPreference: (key: string, value: unknown) => {
    seen.push(`PUT ${key}`);
    rows.set(slot(key), value);
    return Promise.resolve(value);
  },
}));

type AccountRow = { id: string; account_no: string; name: string; status: string };

const s17Config: TableConfig<AccountRow> = {
  screenId: "S17",
  columns: [
    { key: "account_no", label: "Account #", identity: true, sortable: true },
    { key: "name", label: "Name", sortable: true },
    { key: "status", label: "Status" },
  ],
  getRowId: (row) => row.id,
  defaultSort: { sort: "account_no", dir: "asc" },
};

const accounts: AccountRow[] = [
  { id: "a1", account_no: "A-10401", name: "Maria Delgado", status: "current" },
  { id: "a2", account_no: "A-10402", name: "Sam Okafor", status: "past_due" },
];

function mount() {
  return render(
    <DataTable
      config={s17Config}
      state={defaultRequestState(s17Config)}
      onStateChange={() => undefined}
      rows={accounts}
      totalRows={accounts.length}
      loading={false}
      empty={{ title: "t", helper: "h", ctaLabel: "c", onCta: () => undefined }}
    />,
  );
}

/** The chooser lives in a `<details>`; open it the way a pointer would. */
async function openChooser(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByLabelText("Show or hide columns"));
}

/** The header's column labels, in order. The ▲/▼ sort marker is stripped: this
 *  suite is about WHICH columns render and in what ORDER, and a sort glyph
 *  moving is a different test's business. */
function headerText(): string {
  return (document.querySelector("thead")?.textContent ?? "").replace(/[▲▼]/g, "");
}

/** Let the mount-time read settle before asserting on what rendered. */
async function settled(expected: string) {
  await waitFor(() => expect(headerText()).toBe(expected));
}

beforeEach(() => {
  rows.clear();
  seen.length = 0;
  session = { tenant: "silvercreek", user: "alex" };
});

afterEach(cleanup);

describe("DEF-647 · US-SHL-007 TC-3/TC-4 — the column choice survives a REMOUNT", () => {
  it("hiding a column, then unmounting and remounting, keeps it hidden", async () => {
    const user = userEvent.setup();

    const first = mount();
    await settled("Account #NameStatus"); // the declared default set
    await openChooser(user);
    await user.click(screen.getByRole("checkbox", { name: "Status" }));
    expect(headerText()).toBe("Account #Name"); // same-render — passes on the BUG too

    // ── the assertion the shipped tree could not make ──────────────────────
    first.unmount();
    mount();
    await settled("Account #Name");

    // And the chooser itself agrees — reopening it does NOT show the defaults
    // back, which is the sentence the PO wrote: "I have to make the changes
    // every time I again click on that menu - it reset to default".
    await openChooser(user);
    expect(screen.getByRole("checkbox", { name: "Status" })).not.toBeChecked();
  });

  it("stores EXACTLY the ordered array the pure transition returned, under `table.S17.columns`", async () => {
    const user = userEvent.setup();
    mount();
    await settled("Account #NameStatus");
    await openChooser(user);

    // Hide, then re-show: `toggleColumnVisible` appends a re-shown column at
    // the END of the visible order, so the stored ORDER is observable.
    await user.click(screen.getByRole("checkbox", { name: "Name" }));
    await user.click(screen.getByRole("checkbox", { name: "Name" }));
    await waitFor(() =>
      expect(rows.get("silvercreek|alex|table.S17.columns")).toEqual([
        "account_no",
        "status",
        "name",
      ]),
    );

    // …and the order comes back on the next mount, not just the membership.
    cleanup();
    mount();
    await settled("Account #StatusName");
    expect(seen.filter((call) => call.startsWith("GET"))).toEqual([
      "GET table.S17.columns",
      "GET table.S17.columns",
    ]);
  });

  it("a reorder survives a remount too — ↑ is persisted like a hide", async () => {
    const user = userEvent.setup();
    const first = mount();
    await settled("Account #NameStatus");
    await openChooser(user);
    await user.click(screen.getByRole("button", { name: "Move Status up" }));
    expect(headerText()).toBe("Account #StatusName");

    first.unmount();
    mount();
    await settled("Account #StatusName");
  });
});

describe("DEF-647 · the three honest states of a stored preference", () => {
  it("no stored preference yet → the config's declared defaults (BR-SHL-024: unknown key = absent)", async () => {
    mount();
    await settled("Account #NameStatus");
    expect(seen).toEqual(["GET table.S17.columns"]); // asked, and got nothing
  });

  it("a stored key that no longer exists is IGNORED, not rendered and not fatal", async () => {
    // `phone` was a column when this user saved their view; the capability row
    // has since dropped it. Their remaining choice must still apply.
    rows.set("silvercreek|alex|table.S17.columns", ["account_no", "phone", "status"]);
    mount();
    await settled("Account #Status");
    expect(screen.queryByText("phone")).not.toBeInTheDocument();
  });

  it("a stored set missing the identity column renders it anyway (BR-SHL-013)", async () => {
    rows.set("silvercreek|alex|table.S17.columns", ["status"]);
    mount();
    // The identity column is prepended on render — the same invariant
    // `DataTable.test.tsx` asserts for the controlled path.
    await settled("Account #Status");
  });

  it("a stored value of the wrong SHAPE falls back to defaults instead of crashing", async () => {
    rows.set("silvercreek|alex|table.S17.columns", { account_no: true });
    mount();
    await settled("Account #NameStatus");
  });

  it("a read that FAILS leaves the list usable on its defaults", async () => {
    const endpoints = await import("@/api/endpoints");
    vi.spyOn(endpoints, "getUserPreference").mockRejectedValueOnce(new Error("network"));
    mount();
    await settled("Account #NameStatus");
    // A preference is a convenience: a failed read is not an error state.
    expect(screen.queryByText(/failed/i)).not.toBeInTheDocument();
  });
});

describe("DEF-647 · US-SHL-007 TC-7 (isolation) — one user's columns are not another's", () => {
  it("a second user in the same tenant gets the defaults, and the first keeps their choice", async () => {
    const user = userEvent.setup();

    const alex = mount();
    await settled("Account #NameStatus");
    await openChooser(user);
    await user.click(screen.getByRole("checkbox", { name: "Status" }));
    await waitFor(() => expect(rows.has("silvercreek|alex|table.S17.columns")).toBe(true));
    alex.unmount();

    // Priya signs in on the same screen of the same tenant.
    session = { tenant: "silvercreek", user: "priya" };
    const priya = mount();
    await settled("Account #NameStatus"); // her own defaults, not Alex's view
    priya.unmount();

    session = { tenant: "silvercreek", user: "alex" };
    mount();
    await settled("Account #Name");
  });

  it("the same user in another tenant gets that tenant's own (absent) preference", async () => {
    const user = userEvent.setup();
    const first = mount();
    await settled("Account #NameStatus");
    await openChooser(user);
    await user.click(screen.getByRole("checkbox", { name: "Name" }));
    await waitFor(() => expect(rows.has("silvercreek|alex|table.S17.columns")).toBe(true));
    first.unmount();

    session = { tenant: "harborpoint", user: "alex" };
    mount();
    await settled("Account #NameStatus");
    // Nothing was written into the other tenant's slot by the read.
    expect(rows.has("harborpoint|alex|table.S17.columns")).toBe(false);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-007@e879338 + US-SHL-013@EP-SHL-05 + DEF-647
// generated: 2026-08-24 by story-coder (DEF-647 column-preference lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// gates: tsc✔ eslint✔ vitest✔ (see the lane report)
// exceptions: the transport is mocked at the `@/api/endpoints` boundary rather than injected as a prop — a new optional prop nothing passes in production is the DEF-007..010 shape G13 exists to refuse, and the SERVER half of the isolation law is proved for real in 06-backend/tests/test_us_shl_013_user_preferences.py under a NOSUPERUSER/NOBYPASSRLS probe
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
