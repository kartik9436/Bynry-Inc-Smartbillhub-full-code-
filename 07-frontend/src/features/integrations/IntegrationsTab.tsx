// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-001 (EP-INT-01) — the S8 Integrations grid, replacing the
//           declared-absence box. US-INT-013 (seventeen manifests) ·
//           US-INT-018 (a card's operations and their words) · US-INT-019
//           (wave B: the card's ONE action button, and the modal behind it)
//           · US-INT-017 (a coming-soon Connect takes no press, and the
//           server refuses too).
//           Screens: S8 · frames 47.1 (populated) · 48.1 (every card state
//           and its button) · 46.1 (the card when they read from us) · 55.2
//           (not ready yet) · S141 (the modal, ConnectModal.tsx).
// Rules:    BR-INT-001 (one card per provider, one manifest each; a
//           coming-soon Connect is DISABLED at the UI **and** refused at the
//           API — the rule's own words are *"Connect disabled at UI AND
//           API"*; this header said *dashed* until 2026-09-04 and the rule
//           never did, which is how a wireframe hatching reached a customer
//           screen with a rule id beside it) ·
//           BR-INT-002 (⚠ AMENDED 2026-09-16, `DEF-INT-5513`: `Connect` opens
//           the SET-UP SCREEN S147, not the modal — the modal keeps Manage,
//           Disconnect and the test that needs a typed recipient) · BR-INT-028 (a
//           provider is a set of operations, and a multi-operation card
//           carries NO aggregate word) · BR-INT-037 (the cards come from the
//           registry — no provider is named in this file, and adding one adds
//           no React) · B14 rule 21 (Tailwind only; this file is on
//           route-b-migrated.txt) · rule 31 (no database id is ever a visible
//           value) · rule 32 (one sentence per section) · rule 33 (a refusal
//           is five or six words) · rules 5 · 6 (two button sizes; Fix it
//           and Disconnect are danger-tier) · BR-SHL-025 (a read-only role
//           sees the control, disabled, with the reason).
// Tests:    src/features/integrations/IntegrationsTab.test.tsx ·
//           src/features/integrations/ConnectModal.dom.test.tsx
// Impacts:  src/api/integrationsEndpoints.ts (the contract) ·
//           src/features/tenancy/SettingsPage.tsx (the mount; passes
//           `readOnly` since wave B) · the eleven locale catalogues.
// ─────────────────────────────────────────────────────────────────────────
// ⚠ COLOURS (DEF-INT-3580 — filed twice more as DEF-INT-3621 and DEF-INT-3630):
// wave A drew this grid in `text-slate-*`, `bg-white` and `text-lg`, none of
// which the theme declares (tailwind.css sets --color-*: initial and
// --text-*: initial), so every card rendered in the body colour while tsc and
// every toContain assertion passed — the class IS in the DOM. Every utility in
// this file is a token the theme declares (neutral, success, warning, danger,
// info, and the type scale), and src/styles/routeBUtilities.test.ts is the one
// check that knows the difference; the wave B walkthrough reads a state word's
// computed colour so a dead token goes red in a browser, not in a screenshot.
//
// ⚠ THE ACTION BUTTON IS ONE MAP, FROM THE STATE (frame 48.1), NOT SEVEN
// COMPONENTS. Wave A shipped the card without it on purpose — a button wired
// to nothing is hard-won law 2 — and wave B adds it together with the modal
// that honours the press (ConnectModal.tsx).
//
// ⚠ AND `Connect` IS NO LONGER ONE OF THE PRESSES IT HONOURS (`DEF-INT-5513`,
// 2026-09-16). It is a `ButtonLink` to the set-up screen S147, because that
// screen was built, routed and tested by `CR-110-BRC04` wave A and NOTHING
// linked to it — reachable only by typing its address, which is hard-won law
// 2's mirror, and which the PO met on the deployed product as *"it is still
// showing modal - i think routing issue"*. The modal still honours `manage`
// and the test that needs a typed recipient; those screens do not exist yet.
//
// State 7, *Coming soon · W7*,
// draws a Connect that takes no press, **and the server refuses it too**
// (US-INT-017): a disabled button is a convenience; the refusal that matters
// is the one nobody can see.
//
// ⚠ THE STYLE IS r10's, AND THE CARD'S BUTTON IS WHERE IT SHOWS (B14 rule 36,
// PO 2026-09-04). `SMARTBillHub.dc.html` line 7727 draws an integration card's
// action as `btn btn-primary btn-sm` — SMALL, content width, left-aligned —
// and a connected card's as `btn btn-secondary btn-sm`. This file drew it
// `w-full` at the default size, which is a slab across the card rather than a
// button on it, and drew the coming-soon one as a hand-rolled dashed
// rectangle. Both are the kit's `Button` now, at `size="sm"`, and the
// disabled one is disabled rather than hatched: **nothing dashed, monospaced
// or labelled like a diagram ships to a utility user.**
//
// ⚠ AND THE CATEGORY FILTER IS THE KIT'S CHIP. It was a row of raw `<button>`
// pills with their own radius, their own two colours and their own uppercase
// type, while `FilterBar` three directories away already drew r10 rule 12's
// chip correctly — as a constant nobody could import. The chip is
// `components/Chip.tsx` now and both call sites render it (`DEF-3722`).

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { getIntegrationsGrid } from "@/api/integrationsEndpoints";
import type { DisplayState, ProviderCard } from "@/api/integrationsEndpoints";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { BoltIcon, EyeIcon, KeyIcon, PencilIcon } from "@/components/icons";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableFilterConfig, TableRequestState } from "@/components/tableTypes";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

const ALL = "all";

/**
 * The narrow `t` this file's PURE helpers take — the same seam
 * `ConnectionDetailPage` and `MachineKeysPage` already declare, for the same
 * reason: a table config must be buildable with `(key) => key` so its shape can
 * be read (its sort, its column keys) before a screen has an i18n instance.
 * `TFunction`'s real signature is generic over the catalogue and cannot be
 * satisfied by that stub.
 */
type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * The set-up screen's address — **S147 · INT-07**, ONE route for all 28
 * (`BR-INT-037`), the provider's key as its only variable.
 *
 * ⚠ **NO PROVIDER IS NAMED HERE AND NONE EVER MAY BE.** A front end that
 * builds this address only for keys it knows about is a front end that must be
 * edited for connector 29 — the rule wave A's route test was written to assert
 * by opening the screen for a vendor nobody has written.
 *
 * ⚠ **THIS STRING IS NOT THE AUTHORITY FOR THE ADDRESS AND MUST NOT BECOME
 * IT.** `routing/screenIds.ts` declares the route and its ids; the tab's own
 * test resolves what this builder produces THROUGH that registry and asserts
 * it lands on `S147`, so moving the screen without moving this line goes RED
 * on the grid's side rather than leaving the card pointing at a dead address.
 * That is the assertion `DEF-INT-5513` cost — the two halves were each tested
 * at their own address and *"does the button open the screen we built"*
 * belonged to neither file.
 */
function connectorSetupRoute(providerKey: string): string {
  return `/settings/connectors/${providerKey}/configure`;
}

/** S142's connection view — the `View` icon's door. */
function connectorViewRoute(providerKey: string): string {
  return `/settings/integrations/${providerKey}`;
}

/** S144's issued keys — the `Keys` icon's door. */
function connectorKeysRoute(providerKey: string): string {
  return `/settings/integrations/${providerKey}/access`;
}

/** The three dimensions the category chips cannot carry (CON-01 ②, p014). */
const FACETS = ["direction", "state", "environment"] as const;
export type ConnectorFacet = (typeof FACETS)[number];

/**
 * A card's value on one facet, or `null` when the card has none.
 *
 * ⚠ **EVERY ONE OF THESE IS ALREADY IN THE GRID PAYLOAD** — `kicker`,
 * `display_state`/`disposition` and `connection.environment` — which is the
 * blueprint's own point: *"+ Filter ▾ needs no new read"*. Nothing is asked of
 * the server and no `f.<name>` reaches a URL, so `NFR-3`'s server-pagination
 * rule is not engaged: this list is bounded by our 28 manifests rather than by
 * tenant data, which is the same reading the search box already ships under.
 *
 * Pure, so the whole filter is provable without a browser.
 */
export function connectorFacet(card: ProviderCard, facet: string): string | null {
  switch (facet) {
    case "direction":
      return `${card.kicker.initiative}.${card.kicker.direction}`;
    case "state":
      return card.disposition.kind === "coming_soon" ? "coming_soon" : card.display_state;
    case "environment":
      return card.connection === null ? null : card.connection.environment;
    default:
      return null;
  }
}

/**
 * Does this card survive the `+ Filter ▾` panel? AND across dimensions, which
 * is IS-4's own combination rule — applied here in the browser rather than on
 * the server, for the reason above.
 */
export function matchesFacets(card: ProviderCard, applied: Record<string, string>): boolean {
  return Object.entries(applied).every(([facet, value]) => connectorFacet(card, facet) === value);
}

/**
 * ⚠ **THE OPTIONS ARE GENERATED FROM THE CARDS ON SCREEN, NEVER TYPED OUT.**
 * The same rule as the category chips, and for the same reason: the pack
 * hand-listed six categories and drew a seventh card belonging to none of them,
 * so pressing every filter made it disappear. A hand-typed state list would do
 * it again the day a twelfth display state or a third environment arrives —
 * which is the service-list trap `CLAUDE.md` calls hard-won law 2's sibling.
 * First-appearance order, like `payload.categories`.
 */
export function facetOptions(
  cards: readonly ProviderCard[],
  facet: string,
): string[] {
  const seen: string[] = [];
  for (const card of cards) {
    const value = connectorFacet(card, facet);
    if (value !== null && !seen.includes(value)) seen.push(value);
  }
  return seen;
}


/**
 * The card's word, and the only place a state becomes English.
 *
 * Six words for five stored values: `reading_from_us` is COMPUTED by the
 * server for a connection whose operations are all the partner's reads, and it
 * is not a sixth value in `integration_connection.status`. The pack is explicit
 * that it is not a synonym for working — nothing of ours ran, so we cannot
 * claim the connection works, only that somebody has been reading and when.
 */
export function StateWord(props: { state: DisplayState; dot?: boolean }) {
  const { t } = useTranslation();
  const tone: Record<DisplayState, string> = {
    working: "text-success-700",
    not_working: "text-danger-700",
    untested: "text-warning-700",
    reading_from_us: "text-info-700",
    off: "text-neutral-600",
    not_set_up: "text-neutral-600",
  };
  return (
    <span className={`text-sm font-medium ${tone[props.state]}`} data-state={props.state}>
      {/* ── CR-110-BRC04 wave B · the dot the Integration Blueprint draws ──
          Every `VIEW-` frame draws the state as *● Working*, *● Refused* — the
          dot carries the tone so the word does not have to be read to see that
          something is wrong.

          ⚠ **OPT-IN, SO NOT ONE OF THE GRID'S CALL SITES MOVES A PIXEL.** It is
          a new optional prop with a `false` default, exactly the shape
          `Panel`'s own `tone` addition records: every existing caller passes
          nothing and renders byte-for-byte what it rendered before. Hard-won
          law 2 warns about an optional prop NOTHING passes — S142's table
          passes this one, in the same commit.

          ⚠ **AND IT IS `aria-hidden`.** The dot repeats the word beside it, so
          a screen reader that announced both would hear the state twice. The
          colour is decoration here; the word is the fact. */}
      {props.dot === true && (
        <span aria-hidden="true" data-state-dot={props.state}>
          {"● "}
        </span>
      )}
      {t(`integrations.state.${props.state}`)}
    </span>
  );
}

/**
 * **THE NEWEST RUN ON THE CONNECTOR** — column 8, and the one column the CARD
 * could not give you at all.
 *
 * ⚠ **THE MAX, NOT THE FIRST AND NOT THE LAST.** A provider is a SET of
 * operations (`BR-INT-028`) and they run on their own schedules, so `[0]` is
 * the manifest's declaration order rather than a time. Neptune has sixteen.
 * `null` when nothing has ever run, which is a different fact from *ran long
 * ago* and is drawn as an empty cell rather than a zero date.
 */
export function newestRunAt(card: ProviderCard): string | null {
  let newest: string | null = null;
  for (const one of card.operations) {
    if (one.last_run_at === null) continue;
    if (newest === null || one.last_run_at > newest) newest = one.last_run_at;
  }
  return newest;
}

/**
 * The APIs cell — `16 · 14 working`, or a bare `16` before anything has run.
 *
 * ⚠ **THIS REPLACED `OperationLine`, WHICH PUT ONE ROW PER API ON THE CARD**
 * (`DEF-INT-5528`, Product Owner 2026-09-16, verbatim, looking at the grid:
 * *"on nepture - don show all apis on screen - it is breaking the size of the
 * box - you canjust mention the number"*). **Neptune has SIXTEEN operations**,
 * so its card stood sixteen lines tall beside neighbours four lines tall, and
 * **10 of the 28 connectors carry more than three** — it was the default, not
 * one card misbehaving. CON-01 p014 names Neptune by name: *"hiding the
 * per-API lines is the one thing that makes the grid scannable again"*.
 *
 * ⚠ **THE DETAIL IS NOT LOST, IT MOVED TO WHERE IT IS DRAWN.** The connection
 * view already carries every API as a real table — direction, trigger, rate
 * limit, last run — which is what a clerk who wants the per-API truth actually
 * needs, and it is one press away. A card is a summary; a ROW is a tighter one.
 *
 * ⚠ **THE WORD `APIs` LEFT THE VALUE WHEN THE CARD BECAME A ROW (2026-09-17).**
 * On a card the line stood alone and had to name itself; in a table the COLUMN
 * HEADER says `APIs`, so `16 APIs · 14 working` under a header reading `APIs`
 * says it twice. The cell is `16 · 14 working`, and the discriminator below is
 * unchanged — only the noun moved into the header.
 *
 * ⚠⚠ **WHEN THE `· N working` HALF APPEARS IS DECIDED BY *HAS THIS BEEN
 * TESTED*, NOT BY *IS N ABOVE ZERO*, AND THE DIFFERENCE IS A REAL CARD.**
 * Both readings reproduce all nine cards drawn on p012–p013 — a turned-off,
 * not-set-up or never-tested connector has every operation carrying the
 * connection's own word (`selectors.operation_state` cascades it), so nothing
 * is `working` and both rules print the bare `2 APIs` the drawing shows. They
 * part on the card the blueprint does not draw: **a tested connector whose
 * APIs are ALL failing.** Counting alone would print `3 APIs`, which is
 * byte-identical to what an untested card says — the one connector a clerk
 * most needs to tell from *not tested yet* would look exactly like it. Asking
 * whether it was tested prints the honest `3 APIs · 0 working`.
 *
 * The other direction is why the clause is omitted at all: printing
 * `· 0 working` on a connector nobody has tested reads as a failure, which is
 * the opposite of *not tested*.
 */
function apiCountLine(t: Translate, card: ProviderCard): string {
  const total = card.operations.length;
  // `working` and `not_working` are the only two states a RUN produces
  // (`selectors.operation_state`); `not_set_up`, `untested` and `off` are the
  // connection's word cascaded onto every row, and none of them is a verdict.
  const tested = card.operations.some(
    (one) => one.state === "working" || one.state === "not_working",
  );
  const working = card.operations.filter((one) => one.state === "working").length;
  // ⚠ `total`, NOT `count`. i18next treats a `count` variable as a PLURAL
  // request and resolves `…_one` / `…_other` instead of the key as written —
  // so naming it `count` here would make a bare `{{count}}` value depend on
  // two catalogue rows per language for a number that is never pluralised.
  return tested
    ? t("integrations.table.apisWorking", { total, working })
    : t("integrations.table.apis", { total });
}

/** The four acts of the ruling of 2026-09-17, in the order they are drawn. */
const ROW_ACTIONS = ["connect", "view", "edit", "keys"] as const;
export type ConnectorRowAction = (typeof ROW_ACTIONS)[number];

/**
 * **THE ACTIONS CELL, AS ONE MAP FROM THE STATUS — PO ruling 2026-09-17.**
 *
 * Verbatim: *"Action im looking for - Connect, View, Edit, Keys- based on this
 * status will chnage"*, ratified over the full seven-row matrix as *"this is
 * good - please add it"*. The matrix, the supersession chain and what it cost
 * are in `12-governance/02-decision-log.md` under *`CON-01` BECOMES A TABLE*.
 *
 * ⚠⚠ **THREE THINGS THE PRODUCT OWNER AGREED EXPLICITLY. THEY ARE DECISIONS,
 * NOT TASTE, AND A LANE THAT TIDIES ONE AWAY IS UNDOING A RATIFICATION — every
 * check in the repo will pass while it does.**
 *
 *  1. **FOUR ICONS ON EVERY ROW, ALWAYS, IN THIS ORDER. An action never
 *     disappears; it GREYS.** The PO's own reason: *"A row where the icons move
 *     around is a row people have to re-read"*. Hiding a disabled icon to make
 *     the cell tidier is the change this clause exists to refuse.
 *  2. **EVERY GREYED ICON CARRIES ITS REASON** (`BR-SHL-025`). `RowAction`
 *     makes `disabled` and `reason` ONE prop precisely so this cannot be
 *     skipped — there is no boolean to pass — and it is said here rather than
 *     left for the next reader to infer from a prop shape.
 *  3. **An ENABLED icon's tooltip is the action word ALONE** — Connect, View,
 *     Edit, Keys. One word, B14 rule 33. The reason strings belong to greyed
 *     icons and appear nowhere else.
 *
 * ⚠ **`Set up` AND `Fix it` ARE BOTH `Edit` NOW, AND CONNECT SHARES ITS DOOR.**
 * All three opened `S147`; the card gave them three words at three points in a
 * connector's life. Connect and Edit are therefore the same address and are
 * never both live — Connect is the one act available when there is nothing to
 * connect to yet, Edit the one available once there is.
 *
 * ⚠ **`Turn on` / `Turn off` AND `Disconnect` ARE NOT HERE, AND BOTH ABSENCES
 * ARE RULED.** Enabling a connector moved to the connector's own screen, and
 * with it the only destructive tier this cell had — **no icon in this table is
 * red.** Disconnecting destroys every key on a connector and a partner stops
 * working mid-morning, so it stays behind the connector page's confirm dialog
 * where the consequence can be read before it is taken.
 *
 * ⚠ **THE ADAPTER HOLD IS A FIFTH REASON AND IT IS *NOT* IN THE PO's MATRIX —
 * KEPT DELIBERATELY, AND FLAGGED (`DEF-INT-4224`).** The matrix decides
 * enablement BY STATUS. Whether anything in this product can actually DIAL a
 * provider is a different axis, and it is already a ruled refusal: without an
 * adapter, `POST /integrations/{key}/connect` answers *Cannot be connected
 * yet.* at the LAST step, after a clerk has typed a host, a port, a username, a
 * password and a send-from address. The Product Owner met that as *"I cannot
 * add any APIs - nothing ; no test"*. Dropping the hold to match the matrix
 * literally would re-open that defect, so `Connect` keeps it — and this is
 * called out in the change record rather than settled here.
 *
 * Precedence, and it is the card's own order: **the ROLE first** (a viewer
 * cannot act either way, and one sentence explains the whole screen rather than
 * this one row), then the STATUS matrix, then the adapter hold on `Connect`
 * alone.
 *
 * Pure, so all seven rows of the matrix are provable without a browser.
 */
export function connectorActions(
  t: Translate,
  card: ProviderCard,
  opts: { readOnly: boolean },
): Record<ConnectorRowAction, string | null> {
  if (opts.readOnly) {
    const role = t("settings.readOnlyReason");
    return { connect: role, view: role, edit: role, keys: role };
  }
  if (card.disposition.kind === "coming_soon") {
    const notBuilt = t("integrations.rowAction.notBuilt");
    return { connect: notBuilt, view: notBuilt, edit: notBuilt, keys: notBuilt };
  }
  // `CR-198-BRC10` — the PLATFORM holds this provider (one shared Twilio
  // account): nothing to connect, edit or issue; View opens its status and Test.
  if (card.auth?.mode === "platform_holds_ours") {
    const platform = t("integrations.rowAction.platformProvided");
    return { connect: platform, view: null, edit: platform, keys: platform };
  }
  // ⚠ THE ONE QUESTION THE MATRIX TURNS ON IS *DOES A CONNECTION EXIST*, and
  // `display_state === "not_set_up"` is how the server says no. The other five
  // display states are all states a CONNECTION can be in, which is why they
  // share a row: View, Edit and Keys are live the moment there is something to
  // view, edit or issue against.
  if (card.display_state === "not_set_up") {
    const notConnected = t("integrations.rowAction.notConnected");
    return {
      connect: providerIsConnectable(card) ? null : t("integrations.hold.notConnectable"),
      view: notConnected,
      edit: notConnected,
      keys: notConnected,
    };
  }
  // ── DEF-INT-5658 · A DISCONNECTED CONNECTOR OFFERS CONNECT AGAIN ─────────
  // PO ruling 2026-09-17, verbatim: *"if it is disconnected- then you give a
  // connect option - can we do it"*.
  //
  // ⚠ **THE SERVER HAS ALWAYS ALLOWED THIS AND THE SCREEN ASKED A DIFFERENT
  // QUESTION.** `services.connect_with_fields` refuses a second connect only
  // when `existing.enabled or _has_active_credential(existing)` — a
  // disconnected row is neither — and then calls `_reconnect`, which was
  // written and unreachable. So no signed rule needed narrowing: this line
  // asked *does a row EXIST* where the server asks *is a connection LIVE*.
  //
  // ⚠ **WHAT A CLERK MET, AND WHY NO GATE COULD SEE IT.** The card read
  // *● Turned off* in State and *Already connected* on Connect — two
  // statements about one row that cannot both be true — while Edit accepted
  // every field and left the credential null, and rotating a key answered
  // `409`. Every route back in was shut and the one that appeared to work did
  // nothing. Each piece obeyed its own rule exactly (`US-INT-025` keeps the
  // row so history survives; `BR-INT-026` refuses a duplicate), and the
  // contradiction existed only BETWEEN them — which no gate reads, because
  // none reads rendered output (hard-won law 6).
  //
  // ⚠ **NARROWED, NOT REMOVED.** `working`, `untested`, `not_working` and
  // `reading_from_us` are all LIVE connections and still refuse — offering
  // Connect there would trade this defect for a worse one, since
  // `BR-INT-026`'s UNIQUE (tenant, key, environment) is what stops a utility
  // holding two connections to one partner in one environment.
  if (card.display_state === "off") {
    return {
      connect: providerIsConnectable(card) ? null : t("integrations.hold.notConnectable"),
      view: null,
      edit: null,
      keys: null,
    };
  }
  const already = t("integrations.rowAction.alreadyConnected");
  return { connect: already, view: null, edit: null, keys: null };
}

/**
 * Is there anything in this product that could actually make this connection?
 *
 * ⚠ **THIS IS THE FACT SEVEN LIVE CARDS WERE DRAWN WITHOUT (`DEF-INT-4224`).**
 * An adapter is the object that TALKS TO a provider. Without one,
 * `POST /integrations/{key}/connect` answers *Cannot be connected yet.* — at
 * the LAST step, after a clerk has chosen an environment and typed a host, a
 * port, a username, a password and a send-from address. On 2026-09-06 that was
 * seven of the fourteen live cards, and the Product Owner met it as *"I cannot
 * add any APIs - nothing ; no test"*.
 *
 * ⚠ **`adapter_registered` HAS BEEN ON THE WIRE SINCE WAVE A AND NOTHING READ
 * IT.** It is served by `selectors.provider_card`, declared on `ProviderCard`,
 * and set by four test fixtures — and it had no production reader at all, which
 * is hard-won law 2 in its dead-data form: the fact needed to draw an honest
 * card was already being fetched and no screen asked for it.
 *
 * ⚠ **THE SECOND CLAUSE IS NOT AN EXCEPTION, IT IS THE SAME RULE THE SERVER
 * APPLIES.** `Manifest.we_never_dial` (`DEF-INT-4215`) exempts the one
 * relationship where we never place a call: the partner presents a key we
 * issued and reads from us, or posts to us. There is no call for an adapter to
 * make, so none is missing and none ever will be. The server computes it from
 * `initiative` rather than from `auth.mode` — the narrower and safer test — and
 * `operations[].initiative` is on the wire, so this reads THE SAME PREDICATE
 * off the same data rather than guessing at a proxy. No provider is named here
 * (BR-INT-037); an eighth such connector needs no line.
 *
 * ⚠ **IT IS STILL A RULE IN TWO PLACES, WHICH IS A REAL DRIFT RISK AND IS SAID
 * OUT LOUD RATHER THAN LEFT TO BE NOTICED** — the same shape as the service
 * list the front end types out by hand in two files. The durable fix is for the
 * server to serve the verdict, not its ingredients; until it does, this is the
 * honest reading and `holds.test.ts` pins it.
 */
export function providerIsConnectable(card: ProviderCard): boolean {
  if (card.adapter_registered) return true;
  const weNeverDial =
    card.operations.length > 0 && card.operations.every((one) => one.initiative === "them");
  return weNeverDial;
}

/**
 * **THE ACTIONS CELL — four icons, every row, in the ruled order.**
 *
 * ⚠ **AN ENABLED ACTION IS A `RowActionLink` AND A GREYED ONE IS A DISABLED
 * BUTTON, AND THAT SPLIT IS THE KIT'S RATHER THAN THIS SCREEN'S.** All four
 * acts NAVIGATE, so each live one must be a real link — middle-click and the
 * browser's own *open in new tab* are what a clerk with twenty-eight
 * connectors actually uses, and it is the reasoning `Button.tsx` ships
 * `ButtonLink` for. A disabled link is not a thing the platform has, so
 * `RowActionLink` renders the blocked case as a `<button disabled>` carrying
 * the reason — `BR-SHL-025` satisfied without inventing a fake control.
 */
function ActionsCell(props: { card: ProviderCard; readOnly: boolean }) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const blocked = connectorActions(t as Translate, props.card, { readOnly: props.readOnly });
  const key = props.card.key;

  // ⚠ ONE ARRAY, WALKED — never four hand-written JSX blocks. Four blocks is
  // how an action quietly stops being drawn in one state, which is exactly
  // what ruling point 1 forbids, and it is the shape `CLAUDE.md` calls the
  // hand-typed-list trap. The ORDER of this array IS the ruled order.
  const acts: { name: ConnectorRowAction; icon: ReactNode; to: string }[] = [
    { name: "connect", icon: <BoltIcon />, to: connectorSetupRoute(key) },
    { name: "view", icon: <EyeIcon />, to: connectorViewRoute(key) },
    // Connect and Edit share an address on purpose — see `connectorActions`.
    { name: "edit", icon: <PencilIcon />, to: connectorSetupRoute(key) },
    { name: "keys", icon: <KeyIcon />, to: connectorKeysRoute(key) },
  ];

  return (
    // `data-row-actions` is how a test addresses the CELL rather than guessing
    // at the buttons inside it; the accessible NAME is how it addresses each
    // action, which is the same string a screen reader announces (the reason
    // `RowActions` argues against `data-testid` on new call sites).
    <span data-row-actions={key}>
      <RowActions>
        {acts.map((act) => (
          <RowActionLink
            key={act.name}
            label={t(`integrations.rowAction.${act.name}`)}
            icon={act.icon}
            reason={blocked[act.name]}
            to={tenantPath(act.to)}
          />
        ))}
      </RowActions>
    </span>
  );
}

/**
 * **`CON-01` DECLARED — the ten columns the Product Owner approved on
 * 2026-09-17** (*"Im good with these columes - please implment it"*), as one
 * `TableConfig` rather than as markup.
 *
 * ⚠ **NOT ONE OF THE TEN ASKS THE SERVER FOR ANYTHING NEW.** Every field is
 * already in the grid payload `GET /integrations` has served since wave A —
 * checked against `integrationsEndpoints.ts` rather than assumed — so this is a
 * front-end change end to end and `selectors.grid` is untouched.
 *
 * ⚠ **THE CARD'S SUMMARY SENTENCE HAS NO COLUMN, AND THAT IS THE ONE FACT THE
 * MOVE REALLY COSTS.** *"Collect readings and keep the meter list in step."* is
 * a SENTENCE, and a sentence in a cell sets the height of its whole row and
 * wraps at whatever width the column happens to have — the failure
 * `tableTypes.ts` documents at length and the Product Owner found ten times in
 * one sitting on 2026-08-30 (*"why so much text - just show some status"*). It
 * is kept in the DOM on the Connector cell's `title`, so a pointer and a screen
 * reader both still reach it, and it is still the first thing on the
 * connector's own screen. **Keep the fact, lose the paragraph.**
 *
 * ⚠ **SIX OF THE TEN ARE LOCKED AND THREE CAN BE HIDDEN.** `Environment`,
 * `Where` and `Why` are the clerk's to hide; everything else stays, because a
 * connector list with no State or no APIs is not a shorter list, it is a
 * different screen. `locked` is the kit's own flag — see `TableColumnConfig` —
 * and the identity column is locked by `BR-SHL-013` regardless.
 */
export function connectorsTableConfig(
  t: Translate,
  cells: {
    connector: (card: ProviderCard) => ReactNode;
    state: (card: ProviderCard) => ReactNode;
    lastRun: (card: ProviderCard) => ReactNode;
    actions: (card: ProviderCard) => ReactNode;
  },
  filters: TableFilterConfig[],
): TableConfig<ProviderCard> {
  /**
   * A plain value cell.
   *
   * ⚠ THE MARKER IS ON THE CELL EVEN WHEN THE CELL IS EMPTY, which is what
   * lets a test prove *this cell rendered and is blank* apart from *this column
   * is missing*. Those are different defects and only one of them is visible to
   * a `not.toContain`.
   *
   * ⚠ ONE ATTRIBUTE WITH THE NAME AS ITS VALUE, never `data-cell-<name>`.
   * React refuses to render a camelCased custom attribute and warns to the
   * console instead — so `data-cell-lastRun` reaches the DOM as NOTHING while
   * `tsc` and every render pass. A value has no casing rule.
   *
   * ⚠⚠ **`oneLine` IS NOT DECORATION — IT IS WHAT KEEPS A ROW A ROW, AND IT WAS
   * ADDED AFTER MEASURING THE RUNNING SCREEN.** `tableTypes.ts` records the
   * failure at length: a sentence in a cell sets the height of its WHOLE ROW
   * and wraps at whatever width the column happens to have. Measured in a
   * browser at 1440 before this: the `Why` column was allotted **98px**, so
   * *"No connection to the meter cloud."* wrapped to four lines and **Neptune's
   * row stood 122px tall** beside neighbours of 59px — the card's own problem
   * reappearing in a table, which is the one thing the grid→table move was for.
   * Seven of twenty-eight rows were over one line.
   *
   * **The fix is the kit's own prescription — *keep the fact, lose the
   * paragraph*:** the cell is one line with an ellipsis, and the WHOLE sentence
   * is on `title`, so every word stays in the DOM and stays reachable by a
   * pointer and by a screen reader. Nothing is lost; what changes is how much
   * of the row it is allowed to take.
   *
   * ⚠ `block w-48 truncate`, AND ALL THREE ARE LOAD-BEARING. `truncate` alone
   * is `white-space: nowrap`, which in an auto-layout table makes the column
   * grow to the full sentence instead of clipping it — the opposite of the
   * intention; it needs a bound to ellipsize against, and `block` for the bound
   * to apply. **`w-48` (192px) rather than `max-w-xs` (320px), measured:** the
   * 320px cap gave one-line rows and a **1,535px** table; `w-32` (128px) gives
   * one-line rows and the narrowest table that still shows a useful prefix of
   * the sentence, with the whole of it on `title`. A FIXED width also makes the
   * two sentence columns the same on every row, which is what stops the eye
   * re-finding them down the list.
   *
   * ⚠ **`line-clamp-1` IS NOT USED THOUGH IT READS BETTER**: it is not in this
   * theme's emitted stylesheet at all (checked against the BUILT css, not
   * assumed), so it would render as **nothing** while `tsc`, every `toContain`
   * and every gate passed — `DEF-SHL-5088`'s exact shape.
   */
  const text = (value: string | null, mark: string, oneLine = false) => (
    <span
      data-cell={mark}
      className={oneLine ? "block w-32 truncate" : undefined}
      title={oneLine && value !== null ? value : undefined}
    >
      {value ?? ""}
    </span>
  );
  return {
    screenId: "S8",
    getRowId: (card) => card.key,
    // B14 rule 19 — WHAT the search matches, said on the box. The name and the
    // summary, which is what the card's own search matched; never `card.key`,
    // a stored identifier no clerk reads (rule 31).
    searchFields: ["display_name", "summary"],
    searchPlaceholder: "integrations.search",
    filters,
    // ⚠ **`last_run` DESC IS *NOT* THE DEFAULT, DELIBERATELY.** The grid drew
    // in REGISTRATION ORDER — the order the registry declares its manifests —
    // and that is a curated order a clerk learns: email, then messaging, then
    // meters. Opening on *most recently run* would put whatever a nightly job
    // touched at the top and reshuffle the screen daily. `""` is no sort, and
    // `sortConnectors` below returns the payload's own order for it.
    defaultSort: { sort: "", dir: "desc" },
    columns: [
      {
        key: "connector",
        label: t("integrations.column.connector"),
        identity: true,
        cell: cells.connector,
      },
      {
        key: "category",
        label: t("integrations.column.category"),
        locked: true,
        cell: (card) => text(t(`integrations.category.${card.category}`), "category"),
      },
      {
        key: "direction",
        label: t("integrations.column.direction"),
        locked: true,
        // TWO enum fields, FOUR drawn words — *We send* · *We collect* · *They
        // send* · *They read*. The stored value never reaches the screen.
        cell: (card) =>
          text(
            t(`integrations.kicker.${card.kicker.initiative}.${card.kicker.direction}`),
            "direction",
          ),
      },
      { key: "state", label: t("integrations.column.state"), locked: true, cell: cells.state },
      {
        key: "apis",
        label: t("integrations.column.apis"),
        locked: true,
        // ⚠ `data-operations` IS KEPT FROM THE CARD, and it is a *reached the
        // operations fact* marker rather than proof of anything: it was true of
        // the old `<ul>` and is true of this cell, so it can never fail on the
        // question of whether the APIs are LISTED or COUNTED. What proves that
        // is the whole cell text, asserted exactly.
        // ⚠ `whitespace-nowrap` — `16 · 0 working` broke after the dot and
        // rendered as two lines in a 78px column, which is a count pretending
        // to be a sentence. Seen in the browser, not in a test.
        cell: (card) => (
          <span
            className="whitespace-nowrap"
            data-cell="apis"
            data-operations={card.operations.length}
          >
            {apiCountLine(t, card)}
          </span>
        ),
      },
      {
        key: "environment",
        label: t("integrations.column.environment"),
        // ⚠ `connection` IS `null` ON EVERY *Not set up* AND *Coming soon* ROW
        // — 12 of the 28 in the demo tenant. An empty cell, never a dash and
        // never a fabricated word.
        cell: (card) =>
          text(
            card.connection === null
              ? null
              : t(`integrations.environment.${card.connection.environment}`),
            "environment",
          ),
      },
      {
        key: "where",
        label: t("integrations.column.where"),
        // ⚠ **MASKED BY THE SERVER, AND NEVER COMPOSED HERE** (`BR-INT-003`).
        // `DEF-INT-5555` was exactly a host built on the client. `describe` is
        // the whole of what a screen ever gets.
        cell: (card) => text(card.connection?.describe ?? null, "where", true),
      },
      {
        key: "lastRun",
        label: t("integrations.column.lastRun"),
        sortable: true,
        locked: true,
        cell: cells.lastRun,
      },
      {
        key: "why",
        label: t("integrations.column.why"),
        // ⚠ **ONLY ON A FAILING ROW, AND EMPTY — NOT `—`, NOT `OK` — ON EVERY
        // OTHER.** The column exists to be SCANNED FOR RED; a filler character
        // on twenty-seven healthy rows is exactly the noise that defeats it,
        // and B14 rule 32 is the same answer from the other direction.
        cell: (card) =>
          text(
            card.display_state === "not_working" ? (card.connection?.last_test_text ?? null) : null,
            "why",
            true,
          ),
      },
      {
        key: "actions",
        label: t("integrations.column.actions"),
        locked: true,
        cell: cells.actions,
      },
    ],
  };
}

/**
 * The client-side half of the list: search, then the chips, then `+ Filter ▾`,
 * then the sort, then the page.
 *
 * ⚠⚠ **THIS PAGES IN THE BROWSER, AND IT IS A STATED `NFR-3` DEVIATION RATHER
 * THAN AN OVERSIGHT.** `NFR-3` requires server pagination everywhere, and its
 * reason is `T5`: a list whose length grows with a utility's DATA. **This list
 * does not.** Its length is the number of MANIFESTS WE SHIP — 28 today — and it
 * is bounded by our own code: the same number at a 3,000-connection utility and
 * at a 40,000-connection one. `GET /integrations` has never taken a `page`
 * param and is not asked for one here.
 *
 * The blueprint reached the same conclusion about this screen's SEARCH, on p014
 * and in these words: *"At 28 manifests that is defensible, because the list is
 * bounded by our code rather than by tenant data — and it is the same shape
 * NFR-3 forbids, so it should be written down rather than tidied out of
 * sight."* So it is written down, here and in the decision log, rather than
 * tidied out of sight.
 *
 * **The line it must not cross:** the day a connector list becomes per-tenant
 * data — a utility declaring its own connectors — this becomes a server page.
 */
export function visibleConnectors(
  cards: readonly ProviderCard[],
  opts: { category: string; state: TableRequestState; name: (card: ProviderCard) => string },
): ProviderCard[] {
  const needle = opts.state.q.trim().toLowerCase();
  const matched = cards.filter((card) => {
    if (opts.category !== ALL && card.category !== opts.category) return false;
    if (!matchesFacets(card, opts.state.filters)) return false;
    if (needle === "") return true;
    return opts.name(card).toLowerCase().includes(needle);
  });
  if (opts.state.sort !== "lastRun") return matched;
  // ⚠ NULLS LAST IN BOTH DIRECTIONS. *Never run* is not *ran at the beginning
  // of time*: sorting it as an empty string would park every unconnected
  // connector at the top of an ascending sort, which reads as a list of the
  // oldest runs and is not one.
  const dir = opts.state.dir === "asc" ? 1 : -1;
  return [...matched].sort((a, b) => {
    const left = newestRunAt(a);
    const right = newestRunAt(b);
    if (left === right) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    return left < right ? -dir : dir;
  });
}

/**
 * Cells for the DECLARATION-ONLY use of the config — seeding the request state
 * before the screen has a `t`, a tenant path or a row to render.
 *
 * ⚠ It must never reach a real row. `defaultRequestState` reads `defaultSort`
 * and the column KEYS and renders nothing, which is the same seam
 * `ConnectionDetailPage` takes for the same reason.
 */
const EMPTY_CELLS = {
  connector: () => null,
  state: () => null,
  lastRun: () => null,
  actions: () => null,
};

export interface IntegrationsTabProps {
  /** A4 `settings_lookups: View` — an Executive reads; every control is disabled with the reason. */
  readOnly?: boolean;
  /** Test seam, and the same shape every other Settings tab takes. */
  client?: ApiClient;
}

export function IntegrationsTab(props: IntegrationsTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const readOnly = props.readOnly ?? false;
  const [category, setCategory] = useState<string>(ALL);
  const tenantPath = useTenantPath();
  // IS-8 — the tenant's own date format and zone. `Last run` is the only date
  // on this screen and `BR-SHL-023` keeps ONE formatting path for all of them.
  const { timeZone, dateFormat } = useRegional({});

  // ⚠ **ONE STATE OBJECT FOR THE WHOLE TOOLBAR NOW, WHERE THERE WERE THREE.**
  // The grid held `search` in its own `useState`, the `+ Filter ▾` dimensions
  // in a `TableRequestState` it filled with defaults it never used, and the
  // `▦` fact order in a third. `DataTable` speaks exactly one of these
  // (`BR-SHL-011`'s six params), so the screen keeps one and the kit drives it.
  const [state, setState] = useState<TableRequestState>(() =>
    defaultRequestState(connectorsTableConfig((key) => key, EMPTY_CELLS, [])),
  );

  const gridQuery = useQuery({
    queryKey: queryKeys.integrations,
    queryFn: () => getIntegrationsGrid(client),
  });

  // The chips are GENERATED from the categories the registry actually returned.
  // The pack hand-listed six and drew a seventh card that belonged to none of
  // them, so pressing every filter made it disappear; a generated row cannot
  // drift from the rows beneath it.
  const categories = useMemo(
    () => [ALL, ...(gridQuery.data?.categories ?? []).map((row) => row.key)],
    [gridQuery.data],
  );

  // The three dimensions the chips cannot carry, EVERY option of them generated
  // from the rows the server actually returned (see `facetOptions`). A facet
  // with nothing to offer renders no group at all — `offerableFilters` already
  // drops it, which is `DEF-782`'s rule: what cannot be offered is not drawn.
  const facetFilters = useMemo<TableFilterConfig[]>(() => {
    const cards = gridQuery.data?.providers ?? [];
    return FACETS.map((facet) => ({
      name: facet,
      label: t(`integrations.filter.${facet}`),
      options: facetOptions(cards, facet).map((value) => ({
        value,
        // Each facet's words are the ones already in the row, so a chip reads
        // back exactly what the clerk pressed it from.
        label:
          facet === "direction"
            ? t(`integrations.kicker.${value}`)
            : facet === "environment"
              ? t(`integrations.environment.${value}`)
              : value === "coming_soon"
                ? t("integrations.comingSoon")
                : t(`integrations.state.${value}`),
      })),
    }));
  }, [gridQuery.data, t]);

  /** The provider's name, once — the search reads it and so does the cell. */
  const nameOf = useMemo(
    () => (card: ProviderCard) =>
      t(`integrations.provider.${card.key}.name`, { defaultValue: card.display_name }),
    [t],
  );

  const matched = useMemo(
    () => visibleConnectors(gridQuery.data?.providers ?? [], { category, state, name: nameOf }),
    [gridQuery.data, category, state, nameOf],
  );

  // ⚠ THE PAGE IS CUT HERE BECAUSE THE PAGING IS OURS — see
  // `visibleConnectors` for why this list pages in the browser at all, and for
  // the line that would make it a server page.
  const page = useMemo(() => {
    const from = (state.page - 1) * state.per;
    return matched.slice(from, from + state.per);
  }, [matched, state.page, state.per]);

  if (gridQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }

  if (gridQuery.data === undefined) {
    return (
      <FailedWithRetry
        title={t("integrations.failedTitle")}
        reason={refusalText(t, gridQuery.error)}
        onRetry={() => void gridQuery.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  const config = connectorsTableConfig(
    t as Translate,
    {
      // ⚠ **THE ROW'S IDENTITY HOOKS LIVE IN THIS CELL AND NOT ON THE `<tr>`.**
      // `DataTable` owns the row element and puts nothing of a consumer's on it,
      // deliberately — so the identity column carries them, which is also where
      // a reader would look for the row's identity. `ConnectionDetailPage` does
      // the same and for the same reason.
      //
      // ⚠ **THE SUMMARY SENTENCE IS THE `title` AND NOT A SECOND LINE.** See
      // `connectorsTableConfig`: keep the fact, lose the paragraph.
      connector: (card) => (
        <span data-provider={card.key} data-disposition={card.disposition.kind}>
          <Link
            className="text-accent underline"
            to={tenantPath(connectorViewRoute(card.key))}
            title={t(`integrations.provider.${card.key}.summary`, { defaultValue: card.summary })}
            data-connector-link={card.key}
          >
            {nameOf(card)}
          </Link>
        </span>
      ),
      // ⚠ ONE `StateWord`, NOT A SECOND ONE. It is the only place a stored
      // state becomes English, and the dot carries the tone so a row does not
      // have to be READ to see that something is wrong.
      //
      // ⚠ **A COMING-SOON ROW SHOWS ITS STATE, NOT ITS WAVE.** The CARD drew
      // *Coming soon · v2* INSTEAD of a state word, because a card had room for
      // one line and the wave was the more useful of the two. A row has a State
      // column that every other row fills, so leaving it blank on twelve of
      // twenty-eight would read as *we do not know*. The wave is not lost: the
      // actions cell greys all four with *Not built yet*, which is the fact a
      // clerk acts on, and `data-disposition` still carries it for a test.
      // ⚠ `whitespace-nowrap`, AND IT WAS MEASURED RATHER THAN GUESSED. Ten
      // columns squeeze this one to 73px, where *Reading from us* wraps to two
      // lines and takes its whole row to 80px — four of the twenty-eight, all
      // of them the longest state words. A STATE is the fact the eye lands on
      // first, so it is the one cell that must never wrap; the column claims
      // the ~50px it needs and every row is one line.
      state: (card) => (
        <span className="whitespace-nowrap" data-cell="state" data-state-is={card.display_state}>
          <StateWord state={card.display_state} dot />
        </span>
      ),
      lastRun: (card) => {
        const at = newestRunAt(card);
        return (
          <span data-cell="lastRun">
            {at === null ? (
              ""
            ) : (
              <DateCell value={at} timeZone={timeZone} dateFormat={dateFormat} withTime />
            )}
          </span>
        );
      },
      actions: (card) => <ActionsCell card={card} readOnly={readOnly} />,
    },
    offerableFilters(facetFilters),
  );

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-md font-semibold text-neutral-900">{t("integrations.title")}</h2>
          {/* B14 rule 18 as amended: a description caps at 80% of the content
              width. ⚠ `max-w-measure` IS THE NAME — `max-w-[80%]` is the same
              80% in arbitrary-value syntax and is NOT in the built stylesheet,
              so it renders as nothing while `tsc`, every `toContain` and every
              gate pass, because the class IS in the DOM (B14 rule 21, DEF-974). */}
          <p className="max-w-measure text-sm text-neutral-600">{t("integrations.intro")}</p>
        </div>
        {/* ⚠ **THE CATEGORY CHIPS ARE THE ONE PART OF THE TOOLBAR THIS SCREEN
            STILL OWNS.** `UI-RULES 12` is `[Search…] [chips ×] [+ Filter ▾] …
            [▦ Columns]`, and `DataTable` now draws three of the four from the
            declaration — which is the whole reason the ruling's *table only*
            is cheaper than it looks, and is what CON-01's conformance record
            had listed as *"Not built"* for ② and ③. The eleven category chips
            are CON-01 ④ and take a line of their own (*"eleven chips need a
            line to themselves"*, p013); they are not a `TableConfig.filters`
            entry because the drawing gives them their own row and their own
            `All`, and folding them into the `+ Filter ▾` panel would be a
            layout change nobody asked for. */}
        <ChipRow role="group" aria-label={t("integrations.filterLabel")}>
          {categories.map((key) => (
            <ChipToggle
              key={key}
              selected={category === key}
              onClick={() => {
                setCategory(key);
                // A narrower list must not leave the clerk on page four of the
                // old one — the control-that-lies shape `DEF-3504` was raised
                // for. `DataTable` resets the page on ITS OWN controls; this
                // chip row is ours, so it resets it too.
                setState((was) => ({ ...was, page: 1 }));
              }}
              data-category={key}
            >
              {key === ALL ? t("integrations.category.all") : t(`integrations.category.${key}`)}
            </ChipToggle>
          ))}
        </ChipRow>
      </header>

      <DataTable<ProviderCard>
        config={config}
        state={state}
        onStateChange={setState}
        rows={page}
        totalRows={matched.length}
        loading={gridQuery.isPending}
        error={
          gridQuery.isError
            ? { reason: refusalText(t, gridQuery.error), onRetry: () => void gridQuery.refetch() }
            : null
        }
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        // ⚠ **NO `ctaLabel`, SO NO BUTTON, AND THAT IS THE ANSWER RATHER THAN A
        // TIDIER LABEL.** A clerk cannot ADD a connector: the list is the 28
        // manifests we ship (`BR-INT-037`), so an empty list means a filter
        // matched nothing, never that somebody should create something. A CTA
        // here would be a live button onto nothing — `DEF-MET-4764`'s shape.
        empty={{
          title: t("integrations.table.emptyTitle"),
          helper: t("integrations.table.emptyHelper"),
        }}
      />

      {/* ⚠ **BOTH COUNTS, BECAUSE BOTH ARE ON THE WIRE (`DEF-INT-5499`).**
          `counts.connected` had no production reader at all until 2026-09-16 —
          hard-won law 2 in its dead-data form.

          ⚠ THE SECOND SENTENCE IS A FACT AND MUST STAY TRUE WHEN SOMETHING
          NARROWS THE LIST. *Showing every category* is drawn in the unfiltered
          state; the moment a chip, a search or a `+ Filter ▾` dimension is on,
          it says how many rows are actually on screen instead. */}
      <p className="text-xs text-neutral-600">
        {t("integrations.footnote", {
          count: gridQuery.data.counts.providers,
          connected: gridQuery.data.counts.connected,
        })}{" "}
        {category !== ALL || state.q.trim() !== "" || Object.keys(state.filters).length > 0
          ? t("integrations.footnoteShown", {
              shown: matched.length,
              count: gridQuery.data.counts.providers,
            })
          : t("integrations.footnoteAll")}
      </p>
    </section>
  );
}

// ── Lifecycle ────────────────────────────────────────────────────────────
// packet: US-INT-001 (EP-INT-01) · US-INT-013 · US-INT-018 · US-INT-019 · US-INT-017 (wave B)
// generated: 2026-09-03 by the CR-069 wave A build lane · EXTENDED 2026-09-03 by the wave B build lane (the button and the modal)
// checklist: A✔ B✔ C✔ D✔(test · PATCH from the card; the rest through the modal) E✔(mounted from SettingsPage with readOnly) F✔ G✔ H=n/a
// gates: tsc · vitest · G13 (readOnly is now supplied by SettingsPage) · G15/G18 (the catalogue stems above exist in all eleven) · G31 (Tailwind only, and this path is on route-b-migrated.txt) · G69 (no id is a visible value)
// exceptions: `useToast` requires the app's ToastProvider, which App.tsx mounts above every route; the static test wraps its render in one
// status: VERIFIED-UNRATIFIED
// ─────────────────────────────────────────────────────────────────────────
