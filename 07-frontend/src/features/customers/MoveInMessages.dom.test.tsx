// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.33 (lane MVI-WIZ-REV) — the Messaging table of
//           images 45 and 46: SEND · MESSAGE * · TO · CHANNEL · WHEN, the two
//           defaults first, *+ Add message* rows after, *n will send*.
// Defect:   DEF-CUS-6365 — every cell of a default row is the server's.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, AND WHAT EACH CASE DOES ABOUT IT:**
//
//   · **A table that renders while the read is still in flight** would show
//     the right columns with no rows. So the row COUNT is asserted.
//   · **A SEND box that renders ticked for every row** — the boxes are read by
//     their `checked` property, in BOTH directions.
//   · **A default's box left live** is hard-won law 2's mirror: Complete has
//     no parameter for a default. `disabled` is asserted per default box, so
//     the day one is ruled this goes red and names itself — and the added
//     row's box is asserted LIVE, so the case cannot pass by disabling all.
//   · **An added row that never reaches the commit** — `extraMessagesPayload`
//     is asserted on what the clerk picked, and a blank or unticked row is
//     asserted to send nothing.
//   · **A query that ignores its inputs** — the URL the client actually
//     requests is captured and asserted.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { Translator } from "@/features/tenancy/settingsShared";
import i18n from "@/i18n";

import {
  MoveInMessages,
  channelsText,
  defaultMessagesPayload,
  extraMessagesPayload,
  hydrateDefaultChoices,
  hydrateExtraMessages,
  moveInMessagesPath,
  newExtraMessage,
  willSendCount,
} from "./MoveInMessages";
import type { DefaultChoices, ExtraMessageRow, MoveInMessagePlan } from "./MoveInMessages";

afterEach(cleanup);

const t: Translator = (key, params) => i18n.t(key, params);

/** The table body's rows, in order (the kit's `data-editable-row`). */
function bodyRows(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>("[data-editable-row]"));
}

const PLAN: MoveInMessagePlan = {
  served: true,
  results: [
    {
      key: "move_in_welcome",
      channels: ["email", "sms"],
      template: { code: "email_welcome", name: "Welcome — move-in", version: 5 },
    },
    // `DEF-CUS-9743` — the agreement goes out on paper; this utility has
    // published no contract version, so it is queued and holds.
    { key: "service_agreement", channels: ["pdf_print"], template: null },
  ],
};

const TEMPLATES = {
  served: true,
  results: [
    { code: "planned_outage", name: "Planned outage notice" },
    { code: "paperless_welcome", name: "Paperless welcome" },
  ],
};

/** A client that records the path it was asked for. */
function clientServing(plan: MoveInMessagePlan, asked: string[] = []): ApiClient {
  return {
    get: async (path: string) => {
      asked.push(path);
      const data = path.startsWith("/move-ins/message-templates") ? TEMPLATES : plan;
      return { status: 200, data: data as unknown, headers: {} };
    },
  } as unknown as ApiClient;
}

let held: ExtraMessageRow[] = [];
let heldDefaults: DefaultChoices = {};

function mount(props: {
  plan: MoveInMessagePlan;
  asked?: string[];
  category?: string;
  depositTaken?: boolean;
  depositCleared?: boolean;
  to?: string;
  extra?: ExtraMessageRow[];
  coOwners?: string[];
  unitOwner?: string | null;
  visitPlanned?: boolean;
}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Host() {
    const [extra, setExtra] = useState<ExtraMessageRow[]>(props.extra ?? []);
    const [defaults, setDefaults] = useState<DefaultChoices>({});
    held = extra;
    heldDefaults = defaults;
    return (
      <MoveInMessages
        category={props.category ?? "residential"}
        depositTaken={props.depositTaken ?? false}
        depositCleared={props.depositCleared ?? false}
        to={props.to ?? "Kestrel Bakery LLC"}
        extra={extra}
        onExtraChange={setExtra}
        defaults={defaults}
        onDefaultsChange={setDefaults}
        coOwners={props.coOwners ?? []}
        unitOwner={props.unitOwner ?? null}
        visitPlanned={props.visitPlanned ?? false}
        t={t}
        client={clientServing(props.plan, props.asked)}
      />
    );
  }
  return render(
    <QueryClientProvider client={queryClient}>
      <Host />
    </QueryClientProvider>,
  );
}

describe("the Messaging table (images 45, 46)", () => {
  it("draws the drawn heading, fact and five columns", async () => {
    mount({ plan: PLAN });
    await screen.findByText("Welcome · account opened");
    expect(screen.getByText("Messaging")).toBeInTheDocument();
    expect(screen.getByText("Defaults come from Settings · add any other")).toBeInTheDocument();
    const heads = Array.from(document.querySelectorAll("thead th")).map((th) => th.textContent?.trim() ?? "");
    for (const column of ["Send", "Message *", "To", "Channel", "When"]) {
      expect(heads).toContain(column);
    }
    expect(heads).not.toContain("Template");
    expect(heads).not.toContain("What it says");
  });

  it("one row per default the server answered with, in its order, each a FACT", async () => {
    mount({ plan: PLAN });
    await screen.findByText("Welcome · account opened");
    const rows = bodyRows();
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Welcome · account opened");
    expect(rows[0]).toHaveTextContent("Kestrel Bakery LLC · customer");
    // The notification rules screen's own channel words (B14 rule 34).
    expect(rows[0]).toHaveTextContent("Email · Text message");
    expect(rows[0]).toHaveTextContent("On complete");
    expect(within(rows[0]).queryByRole("combobox")).toBeNull();
    expect(rows[1]).toHaveTextContent("Service agreement");
    expect(rows[1]).toHaveTextContent("Printed letter");
    expect(rows[1]).not.toHaveTextContent("—");
    // No published contract: the truth, beside the name — and only there.
    expect(rows[1].querySelector("[data-message-no-template]")).toHaveTextContent("No template");
    expect(rows[0].querySelector("[data-message-no-template]")).toBeNull();
  });

  it("a default's SEND box is disabled, ticked only when it goes out; its remove is held", async () => {
    mount({ plan: PLAN });
    await screen.findByText("Welcome · account opened");
    const [welcome, agreement] = bodyRows();
    const welcomeBox = within(welcome).getByRole("checkbox") as HTMLInputElement;
    const agreementBox = within(agreement).getByRole("checkbox") as HTMLInputElement;
    expect(welcomeBox).toBeDisabled();
    expect(welcomeBox.checked).toBe(true);
    expect(agreementBox).toBeDisabled();
    // `DEF-CUS-9743` — the agreement is SENT, so its box is ticked and the
    // held ✕'s *Sent by default.* is true of both rows.
    expect(agreementBox.checked).toBe(true);
    for (const row of [welcome, agreement]) {
      const remove = row.querySelector("[data-remove-row]") as HTMLButtonElement;
      expect(remove).toBeDisabled();
      expect(remove.title).toBe("Sent by default.");
    }
  });

  it("+ Add message adds image 46's row: Choose…, the customer, Email, On complete — live", async () => {
    mount({ plan: PLAN });
    await screen.findByText("Welcome · account opened");
    fireEvent.click(screen.getByRole("button", { name: "+ Add message" }));
    const rows = bodyRows();
    expect(rows).toHaveLength(3);
    const added = rows[2];
    const box = within(added).getByRole("checkbox") as HTMLInputElement;
    expect(box).not.toBeDisabled();
    expect(box.checked).toBe(true);
    const selects = within(added).getAllByRole("combobox") as HTMLSelectElement[];
    expect(selects).toHaveLength(4);
    expect(selects[0].value).toBe("");
    expect(selects[0]).toHaveTextContent("Choose…");
    expect(selects[1].value).toBe("customer");
    expect(selects[2].value).toBe("email");
    expect(selects[3].value).toBe("on_complete");
    // The added row's ✕ is live; the defaults' are not.
    expect(added.querySelector("[data-remove-row]")).not.toBeDisabled();
  });

  it("the message picker offers the server's templates BY NAME, and the pick reaches the commit", async () => {
    mount({ plan: PLAN, coOwners: ["Arun Mehta"], unitOwner: "Kestrel Holdings", visitPlanned: true });
    await screen.findByText("Welcome · account opened");
    fireEvent.click(screen.getByRole("button", { name: "+ Add message" }));
    const added = bodyRows()[2];
    const [message, to, channel, when] = within(added).getAllByRole("combobox") as HTMLSelectElement[];
    await within(message).findByRole("option", { name: "Planned outage notice" });
    fireEvent.change(message, { target: { value: "planned_outage" } });
    expect(within(to).getByRole("option", { name: "Arun Mehta · co-owner" })).toBeInTheDocument();
    expect(within(to).getByRole("option", { name: "Kestrel Holdings · unit owner" })).toBeInTheDocument();
    fireEvent.change(to, { target: { value: "co_owner:Arun Mehta" } });
    fireEvent.change(channel, { target: { value: "letter" } });
    expect(within(when).getByRole("option", { name: "Day before the visit" })).toBeInTheDocument();
    fireEvent.change(when, { target: { value: "day_before_move_in" } });
    expect(extraMessagesPayload(held)).toEqual([
      {
        template_key: "planned_outage",
        recipient: "co_owner",
        co_owner_name: "Arun Mehta",
        channel: "letter",
        send_when: "day_before_move_in",
      },
    ]);
  });

  it("Day before the visit is offered only while a visit is planned", async () => {
    mount({ plan: PLAN, visitPlanned: false });
    await screen.findByText("Welcome · account opened");
    fireEvent.click(screen.getByRole("button", { name: "+ Add message" }));
    const when = within(bodyRows()[2]).getAllByRole("combobox")[3];
    expect(within(when).queryByRole("option", { name: "Day before the visit" })).toBeNull();
  });

  it("n will send counts each default that goes out and each ticked, chosen added row", async () => {
    mount({ plan: PLAN });
    await screen.findByText("Welcome · account opened");
    // Image 45: both defaults — *2 will send* (`DEF-CUS-9743`).
    expect(document.querySelector("[data-will-send]")).toHaveTextContent("2 will send");
    fireEvent.click(screen.getByRole("button", { name: "+ Add message" }));
    // Nothing chosen yet — a blank row sends nothing.
    expect(document.querySelector("[data-will-send]")).toHaveTextContent("2 will send");
    const message = within(bodyRows()[2]).getAllByRole("combobox")[0];
    await within(message).findByRole("option", { name: "Paperless welcome" });
    fireEvent.change(message, { target: { value: "paperless_welcome" } });
    expect(document.querySelector("[data-will-send]")).toHaveTextContent("3 will send");
    fireEvent.click(within(bodyRows()[2]).getByRole("checkbox"));
    expect(document.querySelector("[data-will-send]")).toHaveTextContent("2 will send");
  });

  it("a read that did not answer SAYS so", async () => {
    mount({ plan: { served: false, results: [] } });
    expect(await screen.findByText("This list could not be read.")).toBeInTheDocument();
    expect(bodyRows()).toHaveLength(0);
  });

  it("the query carries the category and the two deposit answers", async () => {
    const asked: string[] = [];
    mount({ plan: PLAN, asked, category: "commercial", depositTaken: true, depositCleared: true });
    await screen.findByText("Welcome · account opened");
    expect(asked).toContain("/move-ins/messages?category=commercial&deposit_taken=true&deposit_cleared=true");
    expect(asked).toContain("/move-ins/message-templates");
  });

  it("with no name typed yet, TO still names somebody", async () => {
    mount({ plan: PLAN, to: "   " });
    await screen.findByText("Welcome · account opened");
    expect(bodyRows()[0]).toHaveTextContent("The customer · customer");
  });

  it("an unknown key from the server still renders, as its CODE", async () => {
    mount({ plan: { served: true, results: [{ key: "some_new_letter", channels: ["sms"], template: null }] } });
    expect(await screen.findByText("some_new_letter")).toBeInTheDocument();
    expect(bodyRows()[0]).toHaveTextContent("Text message");
  });
});

describe("the pure helpers", () => {
  it("moveInMessagesPath sends booleans the server's `flag()` reads", () => {
    expect(moveInMessagesPath({ category: "", depositTaken: false, depositCleared: false })).toBe(
      "/move-ins/messages?category=&deposit_taken=false&deposit_cleared=false",
    );
  });

  it("channelsText keeps the server's order", () => {
    expect(channelsText(["email", "pdf_print"], t)).toBe("Email · Printed letter");
    expect(channelsText([], t)).toBe("");
  });

  it("extraMessagesPayload sends only ticked rows with a message, and a co-owner's name only for a co-owner", () => {
    const base = newExtraMessage();
    expect(
      extraMessagesPayload([
        { ...base, template_key: "" },
        { ...base, template_key: "x", send: false },
        { ...base, template_key: "y", co_owner_name: "stale" },
      ]),
    ).toEqual([{ template_key: "y", recipient: "customer", channel: "email", send_when: "on_complete" }]);
  });

  it("hydrateExtraMessages distrusts a parked blob", () => {
    expect(hydrateExtraMessages("nope")).toEqual([]);
    const [row] = hydrateExtraMessages([{ template_key: "y", recipient: "martian", channel: "fax", send_when: "never" }]);
    expect(row).toMatchObject({ template_key: "y", recipient: "customer", channel: "email", send_when: "on_complete", send: true });
  });

  it("defaultMessagesPayload sends only a CHANGED default", () => {
    expect(defaultMessagesPayload({})).toEqual([]);
    expect(defaultMessagesPayload({ move_in_welcome: { send: true, channel: null } })).toEqual([]);
    expect(
      defaultMessagesPayload({
        move_in_welcome: { send: false, channel: "email" },
        service_agreement: { send: true, channel: "email" },
      }),
    ).toEqual([
      { key: "move_in_welcome", send: false },
      { key: "service_agreement", send: true, channel: "email" },
    ]);
  });

  it("hydrateDefaultChoices distrusts a parked blob", () => {
    expect(hydrateDefaultChoices("nope")).toEqual({});
    expect(hydrateDefaultChoices({ x: { send: "no", channel: 3 } })).toEqual({
      x: { send: true, channel: null },
    });
  });

  it("willSendCount", () => {
    // Both defaults go out (`DEF-CUS-9743`); a default with no channel does not.
    expect(willSendCount(PLAN.results, [])).toBe(2);
    expect(willSendCount([{ key: "service_agreement", channels: [], template: null }], [])).toBe(0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-190-BRC10 — PO 2026-10-22, *"A: allow untick and channel change per
// move-in"*. The hold the header above describes has EXPIRED for the rows the
// server marks `editable`; the fact rows (deposit receipt / letter) keep it.
// ══════════════════════════════════════════════════════════════════════════
const EDITABLE: MoveInMessagePlan = {
  served: true,
  results: [
    {
      key: "move_in_welcome",
      channels: ["email", "pdf_print"],
      template: { code: "email_welcome", name: "Welcome — move-in", version: 5 },
      editable: true,
      allowed_channels: ["email", "pdf_print"],
    },
    {
      key: "service_agreement",
      channels: ["pdf_print"],
      template: null,
      editable: true,
      allowed_channels: ["pdf_print"],
    },
    { key: "payment_received", channels: ["email"], template: null },
  ],
};

describe("CR-190 — an editable default is a live control", () => {
  it("the welcome's tick is LIVE; unticking it leaves it out of the count and the commit", async () => {
    mount({ plan: EDITABLE });
    await screen.findByText("Welcome · account opened");
    const [welcome, agreement, receipt] = bodyRows();
    const box = within(welcome).getByRole("checkbox") as HTMLInputElement;
    expect(box).not.toBeDisabled();
    expect(box.checked).toBe(true);
    // A FACT row keeps the old hold — asserted so this cannot pass by enabling all.
    expect(within(receipt).getByRole("checkbox")).toBeDisabled();
    expect(within(agreement).getByRole("checkbox")).not.toBeDisabled();
    expect(document.querySelector("[data-will-send]")).toHaveTextContent("3 will send");
    fireEvent.click(box);
    expect(box.checked).toBe(false);
    expect(document.querySelector("[data-will-send]")).toHaveTextContent("2 will send");
    expect(defaultMessagesPayload(heldDefaults)).toEqual([{ key: "move_in_welcome", send: false }]);
  });

  it("a default whose class allows two channels offers them; the pick reaches the commit", async () => {
    mount({ plan: EDITABLE });
    await screen.findByText("Welcome · account opened");
    const [welcome, agreement] = bodyRows();
    const select = within(welcome).getByRole("combobox") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual(["email", "pdf_print"]);
    expect(select.value).toBe("email");
    fireEvent.change(select, { target: { value: "pdf_print" } });
    expect(defaultMessagesPayload(heldDefaults)).toEqual([
      { key: "move_in_welcome", send: true, channel: "pdf_print" },
    ]);
    // One allowed channel is a FACT, not a one-option select (BR-SHL-010).
    expect(within(agreement).queryByRole("combobox")).toBeNull();
    expect(agreement).toHaveTextContent("Printed letter");
  });
});
