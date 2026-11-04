// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   the NEW CONNECT REDESIGN of 2026-09-28 — the review step's four
//           collapsible groups, each with an `Edit ›` (`step5-review.png`).
// Rules:    B14 rules 4, 21, 41, 43, 44 · BR-SHL-025 · hard-won law 2 · law 6
// ───────────────────────────────────────────────────────
//
// ⚠ **THE LOAD-BEARING CASE IS THAT `Edit ›` IS REACHABLE WHILE THE GROUP IS
// CLOSED.** The drawing shows all four collapsed and every one of them
// carrying its link; a link rendered inside `children` would not exist at all
// until a clerk opened the group, which is dead UI that looks perfect in a
// screenshot (hard-won law 2).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Disclosure } from "./Disclosure";

afterEach(cleanup);

function group(props: Partial<Parameters<typeof Disclosure>[0]> = {}) {
  return (
    <Disclosure
      variant="card"
      title="Customer"
      summary="· Jonas Janssen · new · paperless"
      action={
        <a href="/x/new-connect/1" data-edit="customer">
          Edit ›
        </a>
      }
      {...props}
    >
      <p data-detail="">Every field from step 1, read-only.</p>
    </Disclosure>
  );
}

describe("Disclosure — the review group and its Edit link", () => {
  it("is CLOSED by default — the PO ruled it", () => {
    render(group());
    expect(screen.queryByText("Every field from step 1, read-only.")).toBeNull();
    expect(screen.getByRole("button", { name: /Customer/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("the Edit link is reachable while the group is CLOSED", () => {
    render(group());
    const edit = screen.getByRole("link", { name: "Edit ›" });
    expect(edit).toBeVisible();
    expect(edit).toHaveAttribute("href", "/x/new-connect/1");
  });

  it("the Edit link is OUTSIDE the toggle — HTML forbids a link inside a button", () => {
    const { container } = render(group());
    const toggle = container.querySelector("button[aria-expanded]");
    expect(toggle?.querySelector("a")).toBeNull();
    expect(container.querySelector("[data-disclosure-action] a")).not.toBeNull();
  });

  it("pressing the heading opens the detail; pressing it again closes it", async () => {
    const user = userEvent.setup();
    render(group());
    const toggle = screen.getByRole("button", { name: /Customer/ });
    await user.click(toggle);
    expect(screen.getByText("Every field from step 1, read-only.")).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.click(toggle);
    expect(screen.queryByText("Every field from step 1, read-only.")).toBeNull();
  });

  it("pressing Edit does NOT open the group — one target, one act", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn((event: React.MouseEvent) => event.preventDefault());
    render(
      group({
        action: (
          <a href="/x" onClick={onNavigate}>
            Edit ›
          </a>
        ),
      }),
    );
    await user.click(screen.getByRole("link", { name: "Edit ›" }));
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Every field from step 1, read-only.")).toBeNull();
  });

  it("the card variant is its own bordered box, so a stack reads as the drawing's four", () => {
    const html = renderToStaticMarkup(group());
    expect(html).toContain("border border-divider bg-surface");
  });

  it("no action, no wrapper — every caller that predates this is untouched", () => {
    const bare = renderToStaticMarkup(
      <Disclosure title="Charge codes" summary="3 apply · $38.50 base">
        <p>detail</p>
      </Disclosure>,
    );
    expect(bare).not.toContain("data-disclosure-action");
    // The toggle is still the FIRST child of the shell, as it always was.
    expect(bare).toMatch(/^<div class="border-t border-t-divider py-4"><button /);
  });

  it("BR-SHL-025 — a group with nothing behind it is disabled and says why", () => {
    render(group({ unavailableReason: "Nothing captured yet" }));
    const toggle = screen.getByRole("button", { name: /Customer/ });
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveAttribute("title", "Nothing captured yet");
  });

  it("a long summary never pushes Edit off the row", () => {
    // `flex-1` + `min-w-0` on the toggle and `shrink-0` on the action: the
    // link keeps its width and the summary takes the rest.
    const html = renderToStaticMarkup(group());
    expect(html).toContain("min-w-0 flex-1");
    expect(html).toContain('class="shrink-0 pr-4" data-disclosure-action=""');
  });
});
