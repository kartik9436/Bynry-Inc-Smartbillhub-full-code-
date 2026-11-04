// ── Trace ──────────────────────────────────────────────
// Change:   `CR-150-BRC09` task 13 — **THE COMMUNICATION STEP IS ABSORBED INTO
//           REVIEW.** Eight steps became five and `communication` is not one of
//           them; the whole of it folds into step 5 as the editable **Messages**
//           table of `05-prototype/new-connect-redesign-2026-09-28/
//           step5-review.png`, read AS AN IMAGE (B14 rule 42).
//
//           ⚠⚠ **NOTHING IS LOST — THE PO RULED IT IN THOSE WORDS:** *"we dont
//           want any information to be reduced or lost"*. The audit is §0
//           below, field by field, and **it is a deliverable rather than a
//           note**: with the step id gone there is no other screen left that
//           holds any of this, so a field missed here is a field the product
//           no longer has.
//
//           ⚠ **`CommunicationStep` IS KEPT AS A COMPOSITION OF THE TWO PARTS
//           AND IS NO LONGER REACHED.** The five-step list has no
//           `communication` entry, so nothing routes to it. It is left
//           exported deliberately and for ONE commit only — the Model lane's
//           step list and this file land separately, and an export deleted
//           while the wizard still names it breaks the branch for whichever
//           of the two lands first. **It is dead code the day both are in**,
//           and a comment is a note and never a plan (hard-won law 1), so its
//           deletion is a filed row rather than a sentence here.
// Rules:    PO ruling 2026-09-28 — *"we dont want any information to be
//           reduced or lost"* (the fold) · PO ruling 2026-09-16 — *"we have to
//           make it 3 or 3 communciiton default thats - all these 6-8 line
//           items are not required"* (three occasions, not six) · BR-MET-112
//           (nothing is written until the last button) · BR-NOT-013 (no
//           provider adapter exists on any channel — QUEUED is the truest word
//           this product has) · BR-NOT-002 (a contract version is
//           effective-dated and cannot be seeded) · BR-SHL-025 (a control that
//           cannot act is DISABLED WITH ITS REASON) · B14 rules 20, 21, 31, 32,
//           33, 42, 43
// Questions: ⛔ OQ-376 (the platform has no `connection` source kind) — ALL
//           THREE messages are still refused by name and the queue still holds
//           ZERO rows · ⛔ OQ-379 (the quote is recorded and nothing posts it)
//           — message three is refused a second time, by the money guard
// Tests:    NewConnectReviewRedesign.dom.test.tsx ·
//           NewConnectSteps78.dom.test.tsx · NewConnectWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 0 · THE ABSORBED-FIELD AUDIT — EVERY FIELD THE STEP HELD, AND WHERE IT WENT
// ══════════════════════════════════════════════════════════════════════════
// The step had THREE panels. Each is accounted for below, in the order it was
// drawn, and **nothing is dropped**.
//
// ── PANEL 1 · *Who we are telling* — four read-only rows ──────────────────
//   1 Contact            → `WhoWeAreTelling`, rendered INSIDE the Review's
//                          Messages panel. Same value (`draft.owner.name`),
//                          same absence.
//   2 Email              → same, `draft.owner.email`.
//   3 Phone              → same, `draft.owner.phone`.
//   4 Preferred language → same, and still a STATED ABSENCE tracking `OQ-376`.
//                          ⚠ It is NOT defaulted to English: *they chose
//                          English* and *they chose nothing* are different
//                          facts, and `queue_on_commit` reads the TENANT's
//                          default rather than the owner's anyway
//                          (`OQ-CUS-12619`, PO 2026-09-23).
//
// ── PANEL 2 · *What goes out* — six columns over three message rows ───────
//   5 Communication      → the Messages table's MESSAGE column. ⚠ **THE
//                          TICKED-AND-DISABLED CHECKBOX BECOMES A REMOVABLE
//                          ROW, AND THAT REVERSAL IS NOT SILENT** — §1 quotes
//                          the comment it overturns and says which half of it
//                          stopped being true.
//   6 To                 → the TO column, unchanged.
//   7 Channel            → the CHANNEL column, **still a FACT and not the
//                          dropdown the drawing draws** — see §3, which is a
//                          stamped divergence rather than an omission.
//   8 Template           → the TEMPLATE column, and it is now a real CHOICE:
//                          `messages.templates` reaches `_fire_one`'s
//                          `override_template`. Absent still means *the
//                          published default*, drawn as the em dash.
//   9 When               → the WHEN column, *On commit*, unchanged.
//  10 State              → the STATE column, unchanged, and still the row's
//                          OWN reason: *Not queued* · *No published wording* ·
//                          *Not in the books*.
//
// ── PANEL 3 · *Choosing a template* — the picker ──────────────────────────
//  11 Search templates   → inside the `+ Add template` picker, unchanged.
//  12 The picker's six columns (Template · Group · Channel · Variant ·
//     Version · Would be used) → all six, unchanged, inside the picker. The
//     drawing's own note under the button names exactly those six, which is
//     how we know the fold was meant to keep them.
//  13 The empty state    → *No template matches that name.* / *Loading…*,
//                          unchanged.
//  14 The error state    → *The template list did not load.*, unchanged.
//
// ── WHAT GAINED CAPABILITY RATHER THAN LOSING IT ──────────────────────────
//   · The three occasions can now be taken OFF the list (the `x`), and the
//     choice REACHES THE SERVER — `messages.send`, which `queue_on_commit`
//     has taken as its `choices` argument since the messages were built and
//     which no caller had ever filled.
//   · A template can now be PICKED per message (`messages.templates` →
//     `_fire_one`'s `override_template`), where the picker previously only
//     reported which version would be used.
//
// ── WHAT IS NOT HERE, AND WAS NOT HERE BEFORE ─────────────────────────────
//   · `Unit energised` — drawn `WHEN = As each unit activates`, so it never
//     fired on commit even in the picture, and `BR-MET-115` moved it to the
//     work-order screen on 2026-08-25. The server keeps it in
//     `connection_messages.NOT_AT_CREATION` with `moved_to` set. Listing it
//     here would reverse a standing ruling.
//   · The three occasions the PO DROPPED — schedule of works, inspection
//     booked, welcome pack. Dropped by ruling, not by this fold.
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · THE TICK BECOMES A REMOVABLE ROW — AND WHAT THAT REVERSES
// ══════════════════════════════════════════════════════════════════════════
// This file carried a PO-dated comment of 2026-09-28 defending three ticked,
// DISABLED checkboxes. Quoted, because reversing it silently is the thing
// `CLAUDE.md` files defects about:
//
//     "1. **Nothing the clerk chose here could travel.** `commit_connection`
//         does not call `queue_on_commit`, and `CommitPlan` has no member for
//         a tick or a template pick …
//      2. **Nothing queues anyway.** `OQ-376` is open …"
//
// ⚠ **CLAUSE 1 IS FALSE, AND IT WAS ALREADY FALSE WHEN IT WAS WRITTEN.**
// `commit_connection` ends with
// `made["messages"] = queue_messages_on_commit(actor, connection, data.get("messages"))`,
// and `queue_on_commit`'s own signature is `choices: dict | None` with the
// docstring *"step 7's slice of the commit payload — the clerk's ticks and
// their template picks"*. **The DOOR was open the whole time; the WIRE was the
// missing half** — `CommitPlan` had no `messages` member, so `commitPlanOf`
// sent nothing, and the true sentence *"nothing a clerk chose could travel"*
// was a fact about our own payload rather than about the platform. That is
// hard-won law 2: an engine nothing passes anything to is not a feature, and
// the fix is to pass it something, never to grey the control.
//
// ⚠ **CLAUSE 2 IS STILL TRUE AND IS LEFT STANDING ON EVERY ROW.** `OQ-376` is
// OPEN, the platform has no `connection` source kind, the queue holds ZERO
// rows after a real commit, and every STATE cell still says so. **Removing a
// row does not make the other two go out** — it changes what the build
// RECORDS: `_fire_one` answers `not_asked` / `clerk_unticked` instead of
// `not_sent`, *"because a clerk in front of the build outranks a default"* and
// because *we did not send it* and *they asked us not to* are different facts
// a dashboard counts apart. That is a real act with a real audit row, which is
// what makes the control honest rather than decorative.
//
// ⚠ **WHEN `OQ-376` CLOSES, THIS FILE IS STILL WHAT HAS TO MOVE**, and the
// holds here are rules with a clock in them — so the tests assert each refusal
// BY ITS REASON, and the day a reason stops being true the suite goes red and
// names it.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · WHY THE PICKER IS STILL INFORMATIONAL ABOUT VERSIONS
// ══════════════════════════════════════════════════════════════════════════
// The blueprint's one dotted box: *"The template picker names the version that
// would be used and does not render it. Nothing on this screen proves the
// merge fields resolve against a build that does not exist yet."* That is
// unchanged: the *Would be used* column still MARKS the published row, and a
// DRAFT is listed and cannot be chosen — *"Hiding it would send a clerk
// looking for something they can see exists; showing it as choosable would
// queue a letter nobody has approved."* The server sends every row with
// `pickable` and the filtering is deliberately still not done here.
//
// ⚠ **THE CONTRACT ROUTINELY HAS NO ROW, AND THAT IS THE RULE WORKING.**
// `BR-NOT-002` makes every contract version effective-dated and
// `seed_notice_templates` REFUSES to seed one — there is no human in a
// provisioning transaction to choose that date. On a seeded utility the picker
// returns TWO rows, measured, not three. A lane "fixing" that by adding
// `contract_service_agreement` to `SEEDABLE` would publish an undated
// agreement on every tenant.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · ONE STAMPED DIVERGENCE FROM THE DRAWING — THE CHANNEL CELL
// ══════════════════════════════════════════════════════════════════════════
// `step5-review.png` draws CHANNEL as a dropdown on every row (*Email*,
// *Print*, *Email · Print*). **It is built as a FACT, and that is deliberate.**
//
// `queue_on_commit` takes `{send, templates}` and **nothing else** — there is
// no channel override anywhere on the wire, and `Occasion.channel` is a
// property of the OCCASION in `connection_messages.OCCASIONS`. A dropdown here
// would write to a draft field nothing reads and post to a door that would not
// see it: a live control over a dead act, which is hard-won law 2's mirror and
// the exact shape that put five refusing cards on the customer portal's front
// page. **Reported rather than approximated** (UI method §2.5); the fix is a
// channel member on the door, not a `<select>` on this screen.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { CellSelect, CellStatic, TableArray } from "@/components/TableArray";
import { Note } from "@/components/TextBits";

import type { NewConnectDraft } from "./newConnectDraft";
import { portalLanguageOptions } from "./PortalLanguageField";
import { getConnectTemplates } from "./newConnectEndpoints";
import type { ConnectTemplateRow } from "./newConnectEndpoints";
import { AbsentValue, BUILD_MESSAGE_CHANNEL, BUILD_MESSAGE_OCCASION } from "./newConnectShared";
import type { Translator } from "./newConnectShared";
import { StepIntro } from "./newConnectStepKit";

// ══════════════════════════════════════════════════════════════════════════
// THE THREE MESSAGES — the PO's order, and their server codes
// ══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **THE ORDER IS THE PO'S AND IS THE ORDER THEY SAID THEM IN** — the build
 * exists, then the contract, then the cost. `connection_messages.OCCASIONS`
 * carries the same three codes in the same order, deliberately: two clerks
 * reading this table must see the same three rows, and a screen that sorted
 * them itself would be a second opinion about a ruling.
 *
 * ⚠ **`stopKey` IS THE REASON THIS ROW WILL NOT QUEUE, AND IT IS A FACT RATHER
 * THAN A RATIONALE** (B14 rule 33 gives rationale zero words on screen). *Why*
 * the platform cannot file a connection message belongs in the docstring above
 * and in `OQ-376`; what the clerk reads is that it is not queued.
 *
 * ⚠ **`en` AND `channelEn` ARE READ FROM `newConnectShared`, NOT TYPED HERE
 * (`DEF-MET-7805`).** The build DETAIL page names the same seven occasions and
 * the same two channels, and when it was built it printed the raw codes
 * because nothing held the words in one place.
 */
export const MESSAGES = [
  {
    code: "build_created",
    en: BUILD_MESSAGE_OCCASION.build_created,
    channelEn: BUILD_MESSAGE_CHANNEL.email,
    stopKey: "notQueued",
    stopEn: "Not queued",
  },
  {
    code: "contract",
    en: BUILD_MESSAGE_OCCASION.contract,
    channelEn: BUILD_MESSAGE_CHANNEL.pdf_print,
    stopKey: "noWording",
    stopEn: "No published wording",
  },
  {
    code: "quote_and_what_is_owed",
    en: BUILD_MESSAGE_OCCASION.quote_and_what_is_owed,
    channelEn: `${BUILD_MESSAGE_CHANNEL.email} · ${BUILD_MESSAGE_CHANNEL.pdf_print}`,
    stopKey: "noAmount",
    stopEn: "Not in the books",
  },
] as const;

/** Which class each message renders from — the picker's `code` column. */
export const CLASS_OF: Record<string, string> = {
  build_created: "new_connect_confirmed",
  contract: "contract_service_agreement",
  quote_and_what_is_owed: "new_connect_quote",
};

type MessageRow = (typeof MESSAGES)[number];

// ══════════════════════════════════════════════════════════════════════════
// WHO WE ARE TELLING — panel 1, absorbed whole
// ══════════════════════════════════════════════════════════════════════════

/**
 * The owner's contact details, READ-ONLY, as the drawing shows them.
 *
 * ⚠ **READ-ONLY, AND THE DRAWING SHOWS IT READ-ONLY.** An owner's contact
 * details belong to their customer record; a second place to change them is
 * how two addresses come to disagree (hard rule 8's reasoning, one entity
 * over). The values are step 1's own answers — there is no connection and no
 * account yet, so `who_we_are_telling` (which takes a connection) cannot be
 * the source and must not be faked.
 */
export function WhoWeAreTelling(props: { draft: NewConnectDraft; t: Translator }) {
  return (
    <PlainTable data-telling="">
      <tbody>
        <ContactRow
          what={props.t("customers.newConnect.step7.contact", { defaultValue: "Contact" })}
          field="contact"
          value={props.draft.owner.name}
          absent={props.t("customers.newConnect.step7.noOwner", {
            defaultValue: "No owner named yet.",
          })}
          tracks="step-1"
        />
        <ContactRow
          what={props.t("customers.newConnect.step7.email", { defaultValue: "Email" })}
          field="email"
          value={props.draft.owner.email}
          absent={props.t("customers.newConnect.step7.noEmail", {
            defaultValue: "No email on this owner.",
          })}
          tracks="step-1"
        />
        <ContactRow
          what={props.t("customers.newConnect.step7.phone", { defaultValue: "Phone" })}
          field="phone"
          value={props.draft.owner.phone}
          absent={props.t("customers.newConnect.step7.noPhone", {
            defaultValue: "No phone on this owner.",
          })}
          tracks="step-1"
        />
        {/* ⊕ **`DEF-CUS-9195` — STEP 1 ASKS, SO THIS ROW SAYS WHAT WAS PICKED.**
            It read *"Not asked on this build."* while step 1's Communication
            panel asked it; the answer now also travels to the owner's master
            account (`CR-164-BRC10`). ⚠ **NOT DEFAULTED TO ENGLISH:** blank is
            *no preference*, which is a different fact from English. */}
        <tr>
          <td>
            {props.t("customers.newConnect.step7.language", {
              defaultValue: "Preferred language",
            })}
          </td>
          <td data-telling-field="language">
            {props.draft.communication.language.trim() === "" ? (
              <AbsentValue
                reason={props.t("customers.newConnect.step7.noLanguagePicked", {
                  defaultValue: "None picked on step 1.",
                })}
                tracks="step-1"
              />
            ) : (
              (portalLanguageOptions(props.draft.communication.language, props.t).find(
                (option) => option.value === props.draft.communication.language.trim(),
              )?.label ?? props.draft.communication.language)
            )}
          </td>
        </tr>
      </tbody>
    </PlainTable>
  );
}

function ContactRow(props: {
  what: string;
  field: string;
  value: string;
  absent: string;
  tracks: string;
}) {
  return (
    <tr>
      <td>{props.what}</td>
      <td data-telling-field={props.field}>
        {props.value.trim() === "" ? (
          <AbsentValue reason={props.absent} tracks={props.tracks} />
        ) : (
          props.value
        )}
      </td>
    </tr>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE MESSAGES TABLE — panel 2 and panel 3, folded into Review
// ══════════════════════════════════════════════════════════════════════════

/**
 * **`step5-review.png`'s Messages table, with `+ Add template`.**
 *
 * ⚠ **IT IS THE KIT'S `TableArray` AND NOT A SECOND COLLECTION** (B14 rules 20
 * and 43). The charges table on step 4 is the same component; two table
 * arrays for one idea is exactly what the PO raised by name.
 *
 * ⚠ **THE ROWS ARE THE SERVER'S THREE OCCASIONS, NEVER THE DRAFT'S.** What
 * the draft holds is the SUBTRACTIONS (`messagesOff`) and the template picks
 * (`messageTemplates`), for the reason `removedWorkOrderTemplateIds` holds
 * only removals: a copy of the three on the draft would be a second opinion
 * about a PO ruling, free to drift the day a fourth occasion is added. So
 * `onChange` is not how a row goes — `rowRemoveBlocked` and the ✕ write to
 * `messagesOff`, and a removed row LEAVES THE TABLE, which is what the
 * drawing's ✕ does.
 */
export function MessagesFold(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
  client?: ApiClient;
}) {
  const [search, setSearch] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const templates = useQuery({
    queryKey: ["connect-message-templates", search.trim()],
    queryFn: () => getConnectTemplates(search, props.client),
  });
  const rows = templates.data?.rows ?? [];

  /** Every version this message could render from — the picker's own rows for
   *  its class. A DRAFT is listed and is never offered (see §2). */
  function versionsFor(messageCode: string): ConnectTemplateRow[] {
    return rows.filter((row) => row.code === CLASS_OF[messageCode]);
  }

  /** The version a message would use: its class's published row, or none. */
  function usedRow(messageCode: string): ConnectTemplateRow | undefined {
    return versionsFor(messageCode).find((row) => row.pickable);
  }

  const kept = MESSAGES.filter((message) => !props.draft.messagesOff.includes(message.code));
  const removed = MESSAGES.filter((message) => props.draft.messagesOff.includes(message.code));
  const { tenant } = useParams();

  return (
    <>
      <TableArray<MessageRow>
        collection="messages"
        title={props.t("customers.newConnect.review.messages", { defaultValue: "Messages" })}
        rows={kept}
        rowKey={(message) => message.code}
        emptyText={props.t("customers.newConnect.review.noMessages", {
          defaultValue: "No message goes out.",
        })}
        removeLabel={props.t("customers.newConnect.review.removeMessage", {
          defaultValue: "Remove",
        })}
        // ⚠ **THE ✕ WRITES A SUBTRACTION, IT DOES NOT SPLICE A LIST.**
        // `TableArray` hands back the rows it thinks remain; what the draft
        // stores is which occasions were taken OFF, so the codes missing from
        // that array are the answer. Keeping the array itself would freeze
        // today's three against a server tuple free to grow.
        onChange={(next) => {
          const still = new Set(next.map((message) => message.code));
          props.onPatch({
            messagesOff: MESSAGES.filter((message) => !still.has(message.code)).map(
              (message) => message.code,
            ),
          });
        }}
        actions={[
          // ⊕ **`CR-164-BRC10` items 23 / 46 — A ROW IS ADDED IN THE TABLE.**
          // The PO: *"Messages: one table with a template dropdown on each row
          // - this should be table array"*. A row taken off with ✕ comes back
          // through this, in the server's own order; with nothing taken off
          // there is nothing to add and the button says so by being disabled.
          {
            key: "add-message",
            label: props.t("customers.newConnect.review.addMessage", {
              defaultValue: "+ Add message",
            }),
            blockedReason:
              removed.length === 0
                ? props.t("customers.newConnect.review.allMessagesListed", {
                    defaultValue: "Every message is listed.",
                  })
                : undefined,
            onClick: () =>
              props.onPatch({
                messagesOff: props.draft.messagesOff.filter((code) => code !== removed[0]?.code),
              }),
          },
          {
            key: "add-template",
            label: props.t("customers.newConnect.review.addTemplate", {
              defaultValue: "+ Add template",
            }),
            onClick: () => setPickerOpen((open) => !open),
          },
        ]}
        columns={[
          {
            key: "message",
            label: props.t("customers.newConnect.step7.colMessage", {
              defaultValue: "Communication",
            }),
            cell: (message) => (
              <CellStatic name={`message-${message.code}`}>
                {props.t(`customers.newConnect.message.${message.code}`, {
                  defaultValue: message.en,
                })}
              </CellStatic>
            ),
          },
          {
            key: "to",
            label: props.t("customers.newConnect.step7.colTo", { defaultValue: "To" }),
            cell: () => (
              <CellStatic name="message-to">
                {props.draft.owner.name.trim() === ""
                  ? props.t("customers.newConnect.step7.toOwner", { defaultValue: "The owner" })
                  : props.draft.owner.name}
              </CellStatic>
            ),
          },
          {
            key: "channel",
            label: props.t("customers.newConnect.step7.colChannel", { defaultValue: "Channel" }),
            // ⚠ **A FACT, NOT THE DROPDOWN THE DRAWING DRAWS — see §3.** There
            // is no channel member anywhere on the commit's wire, so a
            // `<select>` here would be a control over a dead act.
            cell: (message) => (
              <CellStatic name={`channel-${message.code}`}>
                {props.t(`customers.newConnect.channel.${message.code}`, {
                  defaultValue: message.channelEn,
                })}
              </CellStatic>
            ),
          },
          {
            key: "template",
            label: props.t("customers.newConnect.step7.colTemplate", {
              defaultValue: "Template",
            }),
            // ⚠ **A REAL CHOICE SINCE THIS COMMIT.** `messages.templates`
            // reaches `_fire_one`'s `override_template`; before it, the picker
            // could only REPORT which version would be used. The empty option
            // is *the published default*, which is what every build does
            // today — an em dash in the drawing, and the placeholder here.
            cell: (message) => {
              const chosen = props.draft.messageTemplates[message.code] ?? "";
              const versions = versionsFor(message.code);
              const used = usedRow(message.code);
              if (templates.isPending) {
                return (
                  <CellStatic name={`template-${message.code}`}>
                    <span aria-hidden="true">…</span>
                  </CellStatic>
                );
              }
              if (versions.length === 0) {
                // ⊕ **`DEF-CUS-9198` — SAYS WHAT TO DO, NOT A BARE DASH** (PO
                // item 22, 2026-10-02: *"No template — add in Settings"*).
                // An INSTRUCTION, five words, and the word Settings opens the
                // page where a template is published.
                return (
                  <CellStatic name={`template-${message.code}`}>
                    <span data-template-missing={message.code}>
                      {props.t("customers.newConnect.step7.noTemplate", {
                        defaultValue: "No template — add in",
                      })}{" "}
                      <Link to={`/${tenant ?? ""}/settings/templates`}>
                        {props.t("customers.newConnect.step7.settings", {
                          defaultValue: "Settings",
                        })}
                      </Link>
                    </span>
                  </CellStatic>
                );
              }
              return (
                <CellSelect
                  name={`template-${message.code}`}
                  label={props.t("customers.newConnect.step7.colTemplate", {
                    defaultValue: "Template",
                  })}
                  value={chosen}
                  placeholder={
                    used === undefined
                      ? props.t("customers.newConnect.step6.choosePlaceholder")
                      : `${used.name} · v${used.version}`
                  }
                  options={versions.map((row) => ({
                    value: `${row.code}`,
                    label: `${row.name} · v${row.version}`,
                    // ⚠ **A DRAFT IS LISTED AND CANNOT BE USED** — the
                    // blueprint's own words, kept verbatim in behaviour.
                    disabled: !row.pickable,
                  }))}
                  onChange={(next) =>
                    props.onPatch({
                      messageTemplates:
                        next === ""
                          ? Object.fromEntries(
                              Object.entries(props.draft.messageTemplates).filter(
                                ([code]) => code !== message.code,
                              ),
                            )
                          : { ...props.draft.messageTemplates, [message.code]: next },
                    })
                  }
                />
              );
            },
          },
          {
            key: "when",
            label: props.t("customers.newConnect.step7.colWhen", { defaultValue: "When" }),
            cell: () => (
              // ⊕ `DEF-CUS-9198` — PO ruling Q8 and `BR-MET-115`: the messages
              // go when the request is APPROVED (`connection_messages.
              // fire_on_approval`), never on Create.
              <CellStatic name="message-when">
                {props.t("customers.newConnect.step7.onApproval", { defaultValue: "On approval" })}
              </CellStatic>
            ),
          },
          {
            key: "state",
            label: props.t("customers.newConnect.step7.colState", { defaultValue: "State" }),
            // ⚠ **THE REASON IS A FACT, SIX WORDS OR FEWER (B14 rule 33), AND
            // IT IS THE ROW'S OWN.** Message three is stopped by the MONEY
            // guard before the source-kind call is ever made, deliberately, so
            // that the day `OQ-376` closes the other two start going out and
            // this one does not start asking an owner to pay a figure no
            // ledger holds.
            // ⊕ **`CR-164-BRC10` item 31 — WHAT WILL HAPPEN TO IT, FROM WHAT IS
            // KNOWN BEFORE CREATE.** A message with a published template is
            // *Sent on approval*; one with none cannot be rendered and is
            // *Not sent* until a template exists. The stop reasons the row used
            // to carry (`stopKey`) were fixed guesses written before the
            // approval trigger existed; the request's own Messages tab reports
            // what actually happened.
            cell: (message) => {
              const sendable =
                templates.isPending || usedRow(message.code) !== undefined;
              return (
                <CellStatic name={`state-${message.code}`}>
                  <span data-message-state={sendable ? "on-approval" : "no-template"}>
                    {sendable
                      ? props.t("customers.newConnect.step7.sentOnApproval", {
                          defaultValue: "Sent on approval",
                        })
                      : props.t("customers.newConnect.step7.notSent", {
                          defaultValue: "Not sent",
                        })}
                  </span>
                </CellStatic>
              );
            },
          },
        ]}
      >
        {/* ⊕ `CR-164-BRC10` — the *Taken off* chips are replaced by the table's
            own *+ Add message* (B14 rule 20: one way to add a row). */}
      </TableArray>

      {/* ══════════════════════════════════════════════════════════════
          THE TEMPLATE PICKER — panel 3, absorbed whole and revealed by the
          footer's own button
          ══════════════════════════════════════════════════════════════
          ⚠ **REVEALED IN PLACE RATHER THAN IN A DIALOG.** It holds a TABLE of
          its own and a search, which is the UI method's own test for a screen
          over a modal; and the review step is itself reached inside a wizard,
          so a dialog here would be a modal opened from a flow a clerk is
          already inside. B14 rule 30 was declined deliberately, so there is
          no rule to follow and the estimate precedent — three fields, one
          outcome — is plainly not this. */}
      {pickerOpen && (
        <Panel as="section" data-template-picker-panel="">
          <StepIntro
            title={props.t("customers.newConnect.step7.choosing", {
              defaultValue: "Choosing a template",
            })}
          />
          <TextField
            id="nc_template_search"
            label={props.t("customers.newConnect.step7.searchLabel", {
              defaultValue: "Search templates",
            })}
            value={search}
            onChange={setSearch}
          />
          {templates.isError ? (
            <RefusalStrip className="mt-2">
              {props.t("customers.newConnect.step7.pickerDown", {
                defaultValue: "The template list did not load.",
              })}
            </RefusalStrip>
          ) : (
            <PlainTable className="mt-2" data-template-picker="">
              <thead>
                <tr>
                  <th>
                    {props.t("customers.newConnect.step7.colTemplate", {
                      defaultValue: "Template",
                    })}
                  </th>
                  <th>
                    {props.t("customers.newConnect.step7.colGroup", { defaultValue: "Group" })}
                  </th>
                  <th>
                    {props.t("customers.newConnect.step7.colChannel", { defaultValue: "Channel" })}
                  </th>
                  <th>
                    {props.t("customers.newConnect.step7.colVariant", { defaultValue: "Variant" })}
                  </th>
                  <th>
                    {props.t("customers.newConnect.step7.colVersion", { defaultValue: "Version" })}
                  </th>
                  <th>
                    {props.t("customers.newConnect.step7.colWouldUse", {
                      defaultValue: "Would be used",
                    })}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} data-picker-empty="">
                      <Note>
                        {templates.isPending
                          ? props.t("customers.newConnect.step7.pickerLoading", {
                              defaultValue: "Loading…",
                            })
                          : props.t("customers.newConnect.step7.pickerEmpty", {
                              defaultValue: "No template matches that name.",
                            })}
                      </Note>
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr
                      key={`${row.code}_${row.category}_${row.language}`}
                      data-template-row={row.code}
                    >
                      <td>{row.name}</td>
                      <td>
                        {props.t(`notifications.group.${row.group}`, { defaultValue: row.group })}
                      </td>
                      <td>
                        {props.t(`notifications.channel.${row.channel}`, {
                          defaultValue: row.channel,
                        })}
                      </td>
                      <td>
                        {props.t(`notifications.category.${row.category}`, {
                          defaultValue: row.category,
                        })}
                        {" · "}
                        {props.t(`shell.language.${row.language}`, { defaultValue: row.language })}
                      </td>
                      <td className="tabular-nums" data-template-version={String(row.version)}>
                        {`v${row.version}`}
                        {" · "}
                        {row.pickable
                          ? props.t("customers.newConnect.step7.published", {
                              defaultValue: "Published",
                            })
                          : props.t("customers.newConnect.step7.draft", { defaultValue: "Draft" })}
                      </td>
                      <td data-would-use={row.pickable ? "yes" : "no"}>
                        {row.pickable ? (
                          <span aria-hidden="true">✓</span>
                        ) : (
                          <span aria-hidden="true">—</span>
                        )}
                        <span className="sr-only">
                          {row.pickable
                            ? props.t("customers.newConnect.step7.wouldUseYes", {
                                defaultValue: "Would be used",
                              })
                            : props.t("customers.newConnect.step7.wouldUseNo", {
                                defaultValue: "A draft cannot be used",
                              })}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </PlainTable>
          )}
        </Panel>
      )}
    </>
  );
}

