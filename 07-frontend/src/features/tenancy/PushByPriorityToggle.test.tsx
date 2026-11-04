// CR-187-BRC10 — PO answer 9 (as corrected 2026-10-21): the work-priorities
// card carries a "Phone alert" per row and ONE "Push by priority" switch, OFF
// until a utility turns it on. Both states are drawn from the server's answer.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { LookupEntry } from "@/api/endpoints";

import { PUSH_SETTINGS_KEY, PushByPriorityToggle } from "./PushByPriorityToggle";
import { REFERENCE_CARDS } from "./referenceDataConfig";
import { PUSH_KINDS, pushKindText } from "./SettingsReferenceData";

function render(on: boolean, readOnly = false): string {
  const queryClient = new QueryClient();
  queryClient.setQueryData(PUSH_SETTINGS_KEY, { push_by_priority: on });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <PushByPriorityToggle readOnly={readOnly} />
    </QueryClientProvider>,
  );
}

const t = i18n.t.bind(i18n);

describe("CR-187-BRC10 — push by priority", () => {
  it("the work-priorities card, and only it, carries the push kind", () => {
    const flagged = REFERENCE_CARDS.filter((card) => card.pushKind === true).map((c) => c.code);
    expect(flagged).toEqual(["work_priorities"]);
  });

  it("draws OFF as the server serves it, labelled in three words or fewer", () => {
    const html = render(false);
    expect(html).toContain('data-push-by-priority="off"');
    expect(html).toContain('data-switch-state="off"');
    expect(html).toContain("Push by priority");
    expect(t("settings.reference.pushByPriority.label").split(" ").length).toBeLessThanOrEqual(3);
  });

  it("draws ON, and a read-only viewer cannot press it", () => {
    const html = render(true, true);
    expect(html).toContain('data-switch-state="on"');
    expect(html).toContain("disabled");
  });

  it("names each push kind in words, never the token", () => {
    expect(PUSH_KINDS).toEqual(["new_job", "urgent_assignment", "emergency"]);
    const words = PUSH_KINDS.map((kind) => pushKindText({ push_kind: kind } as LookupEntry, t));
    expect(words).toEqual(["New job", "Urgent", "Emergency"]);
    expect(t("settings.reference.col.pushKind")).toBe("Phone alert");
  });
});
