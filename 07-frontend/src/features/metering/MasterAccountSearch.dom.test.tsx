// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-130-BRC07 part three, lane C2.
// Defect:  DEF-MET-6155 — the owner control searched a table no screen fills.
// Rules:   B14 rule 31 (no database id is a visible value) · B14 rule 33 (a
//          label ≤ 3 words) · B14 rule 43 (one component, three screens)
// ───────────────────────────────────────────────────────
// ⚠ **EVERY MOUNT HERE IS UNDER THE REAL `/:tenant/...` PATH PATTERN.** A
// fixture that mounts a routed component bare in a `MemoryRouter` with no
// tenant route leaves `useParams().tenant` undefined, so every address the
// component builds comes out `//accounts/…` — a protocol-relative URL to
// another host, which reads as a perfectly good string to `toContain` and is a
// broken link. This component renders a `<Link>` to an account, so the trap is
// live here and not theoretical.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MasterAccountSearch, OwnerAccountCard } from "@/features/metering/MasterAccountSearch";
import { OwnerAccountBlock } from "@/features/metering/OwnerAccount";
import type { OwnerAccount } from "@/features/metering/premisesOwnerContract";

const ACCOUNT: OwnerAccount = {
  id: "01a0c23c-bd23-7f85-a7d5-b55bace9a4f3",
  account_no: "AC-2026-00051",
  name: "Ridge Property LLC",
  owns_count: null,
};

/** The words a clerk actually reads, so an assertion is about the screen. */
const t = ((key: string, params?: Record<string, unknown>) => {
  const words: Record<string, string> = {
    "metering.premises.col.owner": "Master a/c",
    "metering.premises.owner.searchLater": "Search by name, or leave it for later…",
    "metering.premises.owner.searchClear": "Search by name, or clear it…",
    "metering.premises.owner.searching": "Searching…",
    "metering.premises.owner.noMatch": "No account matches that.",
    "metering.premises.owner.choose": "Choose",
    "metering.premises.owner.change": "Change",
    "metering.premises.owner.unnamed": "No name recorded",
    "metering.premises.owner.unnumbered": "No number yet",
    "metering.premises.owner.keepTyping": "More matches. Keep typing.",
    "metering.premises.owner.alreadyOwnsOne": "Already owns 1 other property here.",
    "metering.premises.owner.alreadyOwns": `Already owns ${String(params?.count)} other properties here.`,
    "metering.premises.owner.clearingPutsOnList": "Clearing it puts this on Needs an owner.",
    "metering.premises.owner.fact.alsoOwns": "Also owns",
    "metering.premises.owner.fact.accountNo": "Account",
    "metering.premises.owner.fact.name": "Billed to",
    "metering.premises.owner.fact.balance": "Outstanding",
    "metering.premises.owner.ownsNothingElse": "This is their first property here.",
    "metering.premises.owner.balanceUnavailable": "not available",
    "metering.premises.owner.needs_owner": "Needs an owner",
    "metering.premises.owner.needsOwnerWhy": "Nothing can be billed yet.",
    "metering.premises.owner.findParty": "Find an owner",
  };
  return words[key] ?? key;
}) as never;

/** ⚠ THE REAL PATH PATTERN — see the header. */
function mount(node: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/premises/p1"]}>
        <Routes>
          <Route path="/:tenant/premises/:premisesId" element={<>{node}</>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ⚠ **WITHOUT THIS, EVERY TEST AFTER THE FIRST SEES THE PREVIOUS ONE'S DOM.**
// This project does not enable Testing Library's global auto-cleanup, so eight
// of these fifteen failed on *"Found multiple elements"* — a failure that reads
// like a duplicated control on the screen rather than a leaked fixture. The
// jsdom files in this folder all declare it explicitly, for the same reason.
afterEach(cleanup);

function fakeClient(rows: unknown[], total = rows.length) {
  return {
    get: vi.fn(async () => ({ data: { results: rows, count: total } })),
  } as never;
}

describe("MasterAccountSearch — the owner control searches ACCOUNTS", () => {
  it("labels the row with the ONE surviving word and nothing else", () => {
    mount(<MasterAccountSearch value={null} onChange={() => {}} t={t} client={fakeClient([])} />);
    const label = screen.getByText("Master a/c");
    expect(label.textContent).toBe("Master a/c");
    // B14 rule 33: a label is ≤ 3 words. This one is 1, and it is the same word
    // the review step, the property page and the list column render.
    expect(label.textContent!.trim().split(/\s+/).length).toBeLessThanOrEqual(3);
  });

  it("draws the blueprint's own placeholder, and the EDIT form's when editing", () => {
    const { unmount } = mount(
      <MasterAccountSearch value={null} onChange={() => {}} t={t} client={fakeClient([])} />,
    );
    expect(screen.getByPlaceholderText("Search by name, or leave it for later…")).toBeTruthy();
    unmount();
    mount(
      <MasterAccountSearch
        value={null}
        onChange={() => {}}
        t={t}
        client={fakeClient([])}
        placeholderKey="metering.premises.owner.searchClear"
      />,
    );
    expect(screen.getByPlaceholderText("Search by name, or clear it…")).toBeTruthy();
  });

  it("queries /accounts with f.kind=master — NOT /premises-owners", async () => {
    // ⛔ THIS IS THE DEFECT, AS AN ASSERTION. The control issued
    // `GET /premises-owners?q=…` and found nothing, for ever, because no screen
    // can write to that table.
    const client = fakeClient([]);
    mount(<MasterAccountSearch value={null} onChange={() => {}} t={t} client={client} />);
    await userEvent.type(screen.getByPlaceholderText(/Search by name/), "Ridge");
    await waitFor(() => expect((client as never as { get: { mock: { calls: unknown[][] } } }).get.mock.calls.length).toBe(1));
    const [path, options] = (client as never as { get: { mock: { calls: unknown[][] } } }).get.mock.calls[0];
    expect(path).toBe("/accounts");
    const query = (options as { query: Record<string, unknown> }).query;
    expect(query.q).toBe("Ridge");
    expect(query["f.kind"]).toBe("master");
  });

  it("offers a found account and hands the WHOLE account back, never just an id", async () => {
    const onChange = vi.fn();
    mount(
      <MasterAccountSearch
        value={null}
        onChange={onChange}
        t={t}
        client={fakeClient([{ ...ACCOUNT, kind: "master" }])}
      />,
    );
    await userEvent.type(screen.getByPlaceholderText(/Search by name/), "Ridge");
    const choose = await screen.findByRole("button", { name: "Choose" });
    // The NAME and the NUMBER are both offered — a clerk picking an account
    // from a list of ids could not tell two landlords apart.
    expect(screen.getByText(/Ridge Property LLC · AC-2026-00051/)).toBeTruthy();
    await userEvent.click(choose);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: ACCOUNT.id, account_no: "AC-2026-00051" }),
    );
  });

  it("NEVER auto-picks a single result", async () => {
    const onChange = vi.fn();
    mount(
      <MasterAccountSearch
        value={null}
        onChange={onChange}
        t={t}
        client={fakeClient([{ ...ACCOUNT, kind: "master" }])}
      />,
    );
    await userEvent.type(screen.getByPlaceholderText(/Search by name/), "Ridge");
    await screen.findByRole("button", { name: "Choose" });
    // One unambiguous match is still a choice a person makes. Two landlords
    // with similar names are two parties, and picking one bills it.
    expect(onChange).not.toHaveBeenCalled();
  });

  it("says so when nothing matches, rather than drawing an empty space", async () => {
    mount(<MasterAccountSearch value={null} onChange={() => {}} t={t} client={fakeClient([])} />);
    await userEvent.type(screen.getByPlaceholderText(/Search by name/), "Nobody");
    expect(await screen.findByText("No account matches that.")).toBeTruthy();
  });

  it("says so when the search FAILS — which is not the same as no matches", async () => {
    const client = { get: vi.fn(async () => { throw new Error("offline"); }) } as never;
    mount(<MasterAccountSearch value={null} onChange={() => {}} t={t} client={client} />);
    await userEvent.type(screen.getByPlaceholderText(/Search by name/), "Ridge");
    await waitFor(() =>
      expect(document.querySelector('[data-tracks="owner-account-failed"]')).toBeTruthy(),
    );
    // And an empty list is NOT drawn over it: the two states are distinguishable.
    expect(screen.queryByText("No account matches that.")).toBeNull();
  });

  it("says when a search has more than it shows, rather than truncating silently", async () => {
    const rows = Array.from({ length: 8 }, (_, i) => ({
      ...ACCOUNT,
      id: `id-${i}`,
      account_no: `AC-2026-0005${i}`,
    }));
    mount(<MasterAccountSearch value={null} onChange={() => {}} t={t} client={fakeClient(rows, 40)} />);
    await userEvent.type(screen.getByPlaceholderText(/Search by name/), "Ridge");
    expect(await screen.findByText("More matches. Keep typing.")).toBeTruthy();
  });
});

describe("OwnerAccountBlock — the property page reads the count C1 serves", () => {
  // ⛔ **C1 SERVED `owns_premises_count` FOR THIS ROW AND NOTHING READ IT.**
  // Hard-won law 2, found by clicking rather than by a gate: the contract
  // adapter picked the field up, the block went on rendering three facts, and
  // every test passed. These two cases are what would have caught it.
  it("draws `Also owns` when the server sent a count", () => {
    mount(
      <OwnerAccountBlock
        account={{ ...ACCOUNT, owns_count: 3, balance: "0.0000", currency: "USD" }}
        ownerManager={null}
        t={t}
      />,
    );
    expect(document.querySelector('[data-tracks="owner-account-owns"]')).toBeTruthy();
    expect(screen.getByText(/Already owns 3 other properties here\./)).toBeTruthy();
  });

  it("draws NO such row when the server sent no count — not asked is not zero", () => {
    mount(
      <OwnerAccountBlock
        account={{ ...ACCOUNT, owns_count: null, balance: "0.0000", currency: "USD" }}
        ownerManager={null}
        t={t}
      />,
    );
    expect(document.querySelector('[data-tracks="owner-account-owns"]')).toBeNull();
  });
});

describe("OwnerAccountCard — the confirmation the blueprint draws", () => {
  it("shows the ACCOUNT NUMBER and never the row id (B14 rule 31)", () => {
    mount(<OwnerAccountCard account={ACCOUNT} t={t} />);
    expect(screen.getByText("AC-2026-00051")).toBeTruthy();
    // ⛔ The id must not reach the screen in ANY form — this is the assertion
    // `DEF-CUS-3653`'s lesson asks for, made about the field that carries one.
    expect(document.body.textContent).not.toContain(ACCOUNT.id);
  });

  it("links to the account by id in the HREF, under the real tenant path", () => {
    mount(<OwnerAccountCard account={ACCOUNT} t={t} />);
    const link = screen.getByRole("link", { name: "AC-2026-00051" });
    // ⚠ Not `//accounts/…`. A protocol-relative URL is another host, and it
    // satisfies `toContain("/accounts/")` perfectly.
    expect(link.getAttribute("href")).toBe(`/brazosbend/accounts/${ACCOUNT.id}`);
    expect(link.getAttribute("href")!.startsWith("//")).toBe(false);
  });

  it("draws NO owns-line when the server did not send a count", () => {
    mount(<OwnerAccountCard account={ACCOUNT} t={t} />);
    // `null` is NOT ASKED. Rendering "already owns 0" says the opposite of what
    // it means, so nothing is drawn at all.
    expect(document.querySelector('[data-tracks="owner-account-owns"]')).toBeNull();
  });

  it("draws the owns-line the moment a count arrives — the drawn line, wired", () => {
    // ⚠ **THIS IS THE TEST THAT FIRES WHEN THE HOLD EXPIRES** (hard-won law 2).
    // The blueprint draws `Already owns 3 properties · …`; the wire does not
    // carry a count yet. When C1's `premises_ids_owned_by_account` reaches it,
    // this branch is already live and already proved.
    mount(<OwnerAccountCard account={{ ...ACCOUNT, owns_count: 3 }} t={t} />);
    expect(screen.getByText(/Already owns 3 other properties here\./)).toBeTruthy();
  });

  it("names an absent account number rather than printing a dash over an id", () => {
    mount(<OwnerAccountCard account={{ ...ACCOUNT, account_no: null }} t={t} />);
    expect(screen.getByText("No number yet")).toBeTruthy();
    expect(document.body.textContent).not.toContain(ACCOUNT.id);
  });

  it("draws NO Change control in a read-only context", () => {
    mount(<OwnerAccountCard account={ACCOUNT} t={t} />);
    // The honest read-only shape is no button, not a button that refuses.
    expect(screen.queryByRole("button", { name: "Change" })).toBeNull();
  });

  it("Change clears the value and returns to the search", async () => {
    const onChange = vi.fn();
    mount(
      <MasterAccountSearch value={ACCOUNT} onChange={onChange} t={t} client={fakeClient([])} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Change" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
