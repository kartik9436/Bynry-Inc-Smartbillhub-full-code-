// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-SHL-002 (the topbar breadcrumb) — its `it.todo` "(leaf)"
// Rules:   BR-SHL-004 (ancestors link up · the leaf is plain text · the browser
//          tab mirrors the leaf) · B14 rule 31 (never an id on screen)
// Defects: DEF-374 (the shell had no way for a screen to supply a leaf — OPEN
//          from 2026-08-21 until this commit) · DEF-CUS-5939 (the register's
//          head, which is the first caller)
// ───────────────────────────────────────────────────────
// ⚠ **A `.dom` TEST AND NOT A LINE IN `AppShell.test.tsx`, FOR A REASON THAT
// WOULD HAVE MADE THIS CASE INCAPABLE OF FAILING.** That suite renders through
// `renderToStaticMarkup`, which runs NO EFFECTS — and `useCrumbLeaf` publishes
// from an effect. A case written there would have found no leaf, passed its
// negative assertions, and proved nothing about the feature at all (hard-won
// law 7's *looking at the wrong thing*). So the shell is mounted for real here.
//
// **RED PROVED FIRST**, on the pre-fix `AppShell`:
//
//     AssertionError: expected '<nav class="crumbs">…Accounts</nav>'
//     to contain 'Move-outs'
//
// and `document.title` read `Accounts · SMART360 Next` where the leaf's own word
// belongs.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";
import { useCrumbLeaf } from "./crumbLeaf";

afterEach(cleanup);

/** A screen that publishes what it is showing — the register's own shape. */
function ScreenPublishing({ leaf }: { leaf: string | null }) {
  useCrumbLeaf(leaf);
  return <p>the body</p>;
}

function mount(leaf: string | null) {
  return render(
    <MemoryRouter initialEntries={["/brazosbend/accounts"]}>
      <Routes>
        <Route path="/:tenant" element={<AppShell onSignOut={() => undefined} />}>
          <Route path="accounts" element={<ScreenPublishing leaf={leaf} />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

function crumbs(): HTMLElement {
  const nav = document.querySelector("nav.crumbs");
  if (nav === null) {
    throw new Error("no breadcrumb rendered");
  }
  return nav as HTMLElement;
}

describe("DEF-374 — a screen supplies its own breadcrumb leaf", () => {
  it("publishes the leaf after the module crumb, and the module crumb becomes a link", async () => {
    mount("Move-outs");
    await waitFor(() => expect(crumbs()).toHaveTextContent("Move-outs"));
    // `Accounts › Move-outs`, in that order — read as TEXT, because the order
    // is the whole claim and a `toContain` on markup cannot see it.
    expect(crumbs().textContent).toBe("Accounts›Move-outs");
    // BR-SHL-004: the ancestor links back up, tenant-scoped. ⚠ ASSERTED BY
    // ADDRESS. A crumb that LOOKS like a way back and is not is a defect this
    // product has already filed (`DEF-MET-5870`).
    const up = crumbs().querySelector("a");
    expect(up).not.toBeNull();
    expect(up).toHaveAttribute("href", "/brazosbend/accounts");
    expect(up?.textContent).toBe("Accounts");
    // …and the leaf is plain text, never a link.
    const leaf = crumbs().querySelectorAll("span.cur");
    expect(leaf).toHaveLength(1);
    expect(leaf[0].textContent).toBe("Move-outs");
    expect(leaf[0].tagName).toBe("SPAN");
    // BR-SHL-004's other half: the browser tab mirrors the leaf.
    await waitFor(() => expect(document.title).toBe("Move-outs · SMART360 Next"));
    // B14 rule 31 — a WORD, never a key and never an id.
    expect(crumbs().textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
    expect(crumbs().textContent).not.toContain(".");
  });

  it("publishes NOTHING by default, so every other screen's crumb is what it always was", async () => {
    mount(null);
    await waitFor(() => expect(screen.getByText("the body")).toBeInTheDocument());
    // The exact assertion `AppShell.test.tsx` TC-1 makes, restated in a real
    // DOM: one crumb, plain text, and NO anchor. This is the case that says the
    // capability is inert — 137 screens set no leaf and none of them moved.
    expect(crumbs().textContent).toBe("Accounts");
    expect(crumbs().querySelector("a")).toBeNull();
    expect(crumbs().querySelectorAll("span.cur")).toHaveLength(1);
    await waitFor(() => expect(document.title).toBe("Accounts · SMART360 Next"));
  });

  it("takes the leaf away when the screen goes — a crumb must not outlive its screen", async () => {
    const view = mount("Transfers");
    await waitFor(() => expect(crumbs().textContent).toBe("Accounts›Transfers"));
    view.unmount();
    // Remount with a screen that publishes nothing: if the cleanup did not run,
    // the stale word would still be there. This is hard-won law 2's mirror —
    // a control, or a crumb, that goes on pointing at something it left.
    mount(null);
    await waitFor(() => expect(screen.getByText("the body")).toBeInTheDocument());
    expect(crumbs().textContent).toBe("Accounts");
  });
});
