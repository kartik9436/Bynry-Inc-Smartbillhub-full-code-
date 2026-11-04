// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-INT-5658 — a connector a clerk has DISCONNECTED could never be
//          reconnected. Reproduced on the live stack at 2.294.1.
// Ruling:  PO 2026-09-17, verbatim: *"if it is disconnected- then you give a
//          connect option - can we do it"*.
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE BACKEND ALREADY ALLOWED THIS, WHICH IS THE PART THAT MAKES THE FIX
 * SMALL AND THE BUG SO HARD TO SEE.** `services.connect_with_fields` refuses a
 * second connect only when `existing.enabled or _has_active_credential(existing)`
 * — and a DISCONNECTED row is neither. It then falls through to `_reconnect`,
 * which has been written and waiting the whole time. **No signed rule needed
 * narrowing; the screen was simply never asked the same question the server
 * asks.**
 *
 * The screen asked *does a connection row EXIST* (`display_state !==
 * "not_set_up"`) and held Connect with *"Already connected"* for every other
 * state — including `off`, which is precisely *disconnected*. So a card read
 * **"● Turned off"** in its State column and **"Already connected"** on its
 * Connect button: two statements about one row that cannot both be true.
 *
 * ⚠ **AND THE OTHER TWO DOORS LOOKED OPEN AND WERE NOT** — Edit accepted all
 * four fields and *Save and test*, then left the credential null; rotating a
 * key answered `409`. So every route back in was shut, and the one that
 * appeared to work silently did nothing.
 *
 * Nothing caught it because each piece obeys its own rule exactly — disconnect
 * keeps the row so history survives (`US-INT-025`), connect refuses a provider
 * that already has one (`BR-INT-002`) — and **the contradiction exists only
 * between them.** No gate in this repo reads rendered output (law 6).
 */
import { describe, expect, it } from "vitest";

import { connectorActions } from "@/features/integrations/IntegrationsTab";
import type { ProviderCard } from "@/api/integrationsEndpoints";

const t = ((key: string) => key) as never;

/** A card in each state, minimal but shaped as the server serves it. */
function card(display_state: string): ProviderCard {
  return {
    provider_key: "email_smtp",
    display_name: "Custom SMTP",
    display_state,
    disposition: { kind: "live" },
    adapter_registered: true,
    we_never_dial: false,
  } as unknown as ProviderCard;
}

describe("DEF-INT-5658 · a disconnected connector offers Connect again", () => {
  it("offers Connect when the connection is turned off", () => {
    // ⚠ `off` IS the disconnected state — `selectors.display_state` returns it
    // for "the connection turned off". A hold here is the defect.
    const actions = connectorActions(t, card("off"), { readOnly: false });
    expect(actions.connect).toBeNull();
  });

  it("still refuses Connect on a LIVE connection", () => {
    // The refusal is not removed, only narrowed. A working connector must not
    // offer Connect — that is the `BR-INT-026` uniqueness the server enforces,
    // and widening past it would trade one defect for a worse one.
    expect(connectorActions(t, card("working"), { readOnly: false }).connect).not.toBeNull();
    expect(connectorActions(t, card("untested"), { readOnly: false }).connect).not.toBeNull();
  });

  it("keeps View, Edit and Keys live on a turned-off connection", () => {
    // There is still a row to look at, and its history is why disconnect keeps
    // it (`US-INT-025`). Offering Connect must not take the other three away.
    const actions = connectorActions(t, card("off"), { readOnly: false });
    expect(actions.view).toBeNull();
    expect(actions.edit).toBeNull();
    expect(actions.keys).toBeNull();
  });

  it("a read-only role is still refused everything", () => {
    const actions = connectorActions(t, card("off"), { readOnly: true });
    expect(actions.connect).not.toBeNull();
  });
});
