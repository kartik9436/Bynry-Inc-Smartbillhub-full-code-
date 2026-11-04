// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 — **STEP 3 OF FOUR,
//           `Schedule`**, built from `Step3Schedule.png` and `MasterStep3.png`
//           AS IMAGES (B14 rule 42).
// Rules:    **BR-CUS-1099** (PO 2026-09-25, verbatim: *"So we warn user , but
//           we dont stop user - We can't send a certified notice — a final-tier
//           cut isn't lawful without one"*) · **BR-CUS-1098** (one work order
//           per affected SERVICE POINT) · BR-CUS-100 (the SEND and the PROOF
//           are two different records) · BR-CUS-039 · `OQ-CUS-1810` (the
//           earliest lawful cut, computed server-side) · B14 rules 20, 21, 31,
//           32, 33, 43, 44
// Tests:    ../../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · THE STEP IS STACKED AND HAS NO SIDE PANELS — ITEM 3.5
// ══════════════════════════════════════════════════════════════════════════
// The five-step step 3 drew a two-column layout with the field work as a FORM
// in the right-hand panel. Both drawings here stack: `Notice`, then `Who goes`
// as a TABLE ARRAY, full width. The field work is rows because it IS rows —
// `BR-CUS-1098` gives a master account **one work order per affected service
// point**, which may be twenty-five, and twenty-five copies of a form is not a
// form.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · `No proof, no cut` BECAME A WARNING — `BR-CUS-1099`
// ══════════════════════════════════════════════════════════════════════════
// **The screen still asks for the proof; it no longer refuses.** A clerk may
// schedule a cut with no proof of certified service recorded, and what the
// product captures is that none was recorded, who scheduled it and when.
//
// ⚠ **WHAT MAKES THIS RULING DIFFERENT FROM ITS FOUR SIBLINGS, RECORDED SO
// NOBODY READS IT AS THE SAME THING:** the others are about a CUSTOMER's
// circumstances and the record shows the utility considered them. This is a
// legal precondition on the utility's OWN act, so **here the record protects
// the UTILITY** and its absence is the utility's own exposure. None of that
// reasoning appears on screen (B14 rule 33 — rationale is zero words).
//
// ⚠ **A SECOND REFUSAL SITS BESIDE IT AND IS NOT RULED ON.**
// `assert_service_proved` also raises `tier_3_proof_not_certified` when the
// recorded channel is not certified mail (`BR-CUS-039`). The PO's words are
// about the ABSENCE of proof and say nothing about another channel, so that
// refusal is **not** read as ruled on and this screen does not soften it: the
// channel list still marks certified mail as the one a final-tier cut needs.
//
// ⚠ **AND WE STILL CANNOT SEND A CERTIFIED NOTICE AT ALL.** The notice is
// served outside the product and its proof is typed in by a person. That
// limitation exists today, is already filed, and is NOT what the ruling
// changed — stated here so a reader does not think it was fixed.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · ⛔ NOTHING HERE RAISES A WORK ORDER, AND THE BUTTON SAYS SO
// ══════════════════════════════════════════════════════════════════════════
// The drawing puts `+ Raise work order` in the `WORK ORDER` cell of a row whose
// visit is `Work order`. **`disconnects.VISIT_NOT_SCHEDULED` records that
// nothing in this product books the visit**, and `apps/work/from_flows`'s
// `FLOW_KINDS` holds six kinds — `service_request`, `move_out`, `move_in`,
// `transfer`, `reconnect`, `meter_read` — and `propose()` **refuses anything
// else BY NAME**. A cut is not one of the six.
//
// **So the control is DISABLED and carries its reason** (`BR-SHL-025`), rather
// than being drawn live over a door that does not exist. That is hard-won law
// 2's mirror answered the only honest way: a live control that does nothing is
// worse than a refused one that says what is missing. **The row's VISIT choice
// is still real and is still recorded** — the clerk says a crew must go, and
// the raise is what is not built.
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import { WarningBox } from "@/components/WarningBox";

import { DisconnectTableArray } from "../DisconnectTableArray";
import type { DisconnectArrayColumn } from "../DisconnectTableArray";
import { AUDIENCE_OCCUPANTS, AUDIENCE_OWNER, VISIT_KINDS, workOrderCount } from "../disconnectDraft";
import type {
  DisconnectDraft,
  DisconnectRecipientRow,
  DisconnectVisitRow,
  VisitKind,
} from "../disconnectDraft";
import { PROOF_CHANNELS, SERVICE_CHANNELS } from "../../transferDisconnectShared";
import type { Translator } from "../../transferDisconnectShared";
import type { CutFloor } from "../../transferDisconnectEndpoints";
import type { DisconnectNoticeRow } from "../disconnectNotices";

export interface ScheduleStepProps {
  draft: DisconnectDraft;
  onPatch: (next: Partial<DisconnectDraft>) => void;
  onPatchProof: (next: Partial<DisconnectDraft["proof"]>) => void;
  t: Translator;
  dateFormat: RegionalDateFormat;
  /** The notices already sent on this account, newest first. */
  notices: readonly DisconnectNoticeRow[];
  /** The earliest lawful cut, computed by `apps/customers/cut_date.py`.
   *  ⚠ **NEVER ENFORCED** — PO, verbatim, closing `OQ-CUS-1810`: *"give a
   *  message but allow it"*. No `min` is set on the input and no validator
   *  reads this. */
  cutFloor: CutFloor | null;
  master: boolean;
  occupants: number | null;
}

export function ScheduleStep(props: ScheduleStepProps) {
  const t = props.t;
  const lastSent = props.notices[0] ?? null;
  const proofMissing = props.draft.proof.channel === "" && props.draft.proof.reference.trim() === "";

  function setVisits(rows: DisconnectVisitRow[]): void {
    props.onPatch({ visits: rows });
  }
  function patchVisit(index: number, next: Partial<DisconnectVisitRow>): void {
    setVisits(props.draft.visits.map((row, i) => (i === index ? { ...row, ...next } : row)));
  }
  function setRecipients(rows: DisconnectRecipientRow[]): void {
    props.onPatch({ recipients: rows });
  }
  function patchRecipient(index: number, next: Partial<DisconnectRecipientRow>): void {
    setRecipients(props.draft.recipients.map((row, i) => (i === index ? { ...row, ...next } : row)));
  }

  const visitColumns: DisconnectArrayColumn<DisconnectVisitRow>[] = [
    {
      key: "point",
      label: t("customers.disconnect.schedule.colPoint", { defaultValue: "Service point" }),
      cell: (row) => <span className="font-semibold">{row.label}</span>,
    },
    {
      key: "meter",
      label: t("customers.disconnect.schedule.colMeter", { defaultValue: "Meter" }),
      cell: (row) => <span>{row.meter === "" ? "—" : row.meter}</span>,
    },
    {
      key: "visit",
      label: t("customers.disconnect.schedule.colVisit", { defaultValue: "Visit" }),
      cell: (row, index) => (
        <SelectField
          id={`disconnect-visit-${index}`}
          labelHidden
          label={t("customers.disconnect.schedule.colVisit", { defaultValue: "Visit" })}
          value={row.visit}
          placeholder={t("customers.disconnect.schedule.pickVisit", { defaultValue: "Choose" })}
          onChange={(value) => patchVisit(index, { visit: value as VisitKind })}
          options={VISIT_KINDS.map((kind) => ({
            value: kind.code,
            label: t(`customers.disconnect.visit.${kind.code}`, { defaultValue: kind.en }),
          }))}
        />
      ),
    },
    {
      key: "instruction",
      label: t("customers.disconnect.schedule.colInstruction", { defaultValue: "Instruction" }),
      cell: (row, index) =>
        row.visit === "work_order" ? (
          <TextField
            id={`disconnect-instruction-${index}`}
            label={t("customers.disconnect.schedule.colInstruction", {
              defaultValue: "Instruction",
            })}
            value={row.instruction}
            onChange={(value) => patchVisit(index, { instruction: value })}
          />
        ) : (
          <span className="text-neutral-700">—</span>
        ),
    },
    {
      key: "work_order",
      label: t("customers.disconnect.schedule.colWorkOrder", { defaultValue: "Work order" }),
      cell: (row) =>
        row.visit !== "work_order" ? (
          <span className="text-neutral-700">—</span>
        ) : row.workOrder !== "" ? (
          <span className="font-semibold">{row.workOrder}</span>
        ) : (
          // `DEF-CUS-9631` — the row is RAISED by the commit (`visits` on
          // `POST /disconnects/schedule`, Work's seventh flow door), so the
          // cell says when rather than offering a button. It read a disabled
          // *+ Raise work order* with *A cut cannot raise one yet.* — true
          // until this build, and the confirm step promised the job anyway.
          <span className="text-neutral-700" data-raised-on-schedule="">
            {t("customers.disconnect.schedule.raisedOnSchedule")}
          </span>
        ),
    },
  ];

  const recipientColumns: DisconnectArrayColumn<DisconnectRecipientRow>[] = [
    {
      key: "audience",
      label: t("customers.disconnect.schedule.colAudience", { defaultValue: "Who is notified" }),
      cell: (row) => (
        <span className="font-semibold">
          {t(`customers.disconnect.audience.${row.audience}`, {
            defaultValue: row.audience === AUDIENCE_OWNER ? "The owner" : "Occupying accounts",
          })}
        </span>
      ),
    },
    {
      key: "count",
      label: t("customers.disconnect.schedule.colHowMany", { defaultValue: "How many" }),
      cell: (row) => (
        <span className={row.count > 1 ? "font-semibold text-danger-700" : undefined}>
          {row.count}
        </span>
      ),
    },
    {
      key: "channel",
      label: t("customers.disconnect.schedule.colServed", { defaultValue: "How it is served" }),
      cell: (row, index) => (
        <SelectField
          id={`disconnect-recipient-channel-${index}`}
          labelHidden
          label={t("customers.disconnect.schedule.colServed", {
            defaultValue: "How it is served",
          })}
          value={row.channel}
          placeholder={t("customers.disconnect.schedule.pickChannel", {
            defaultValue: "Choose",
          })}
          onChange={(value) => patchRecipient(index, { channel: value })}
          options={SERVICE_CHANNELS.map((channel) => ({
            value: channel.code,
            label: t(`customers.disconnect.channel.${channel.code}`, {
              defaultValue: channel.en,
            }),
          }))}
        />
      ),
    },
    {
      key: "reference",
      label: t("customers.disconnect.schedule.colReference", { defaultValue: "Proof reference" }),
      cell: (row, index) => (
        <TextField
          id={`disconnect-recipient-reference-${index}`}
          label={t("customers.disconnect.schedule.colReference", {
            defaultValue: "Proof reference",
          })}
          value={row.reference}
          onChange={(value) => patchRecipient(index, { reference: value })}
        />
      ),
    },
  ];

  const cutDate = (
    <DatePickerField
      id="disconnect-cut-on"
      label={t("customers.disconnect.schedule.cutOn", { defaultValue: "Scheduled cut date" })}
      value={props.draft.cutOn}
      onChange={(value) => props.onPatch({ cutOn: value })}
      required
      dateFormat={props.dateFormat}
      // ⚠ NO `min`. PO, closing `OQ-CUS-1810`: *"give a message but allow it"* —
      // `CutFloor.enforced` is `false` on every answer and no validator reads it.
      help={
        props.cutFloor?.earliest_lawful_cut == null
          ? undefined
          : t("customers.disconnect.schedule.earliest", {
              defaultValue: "Earliest lawful cut {{date}}",
              date: props.cutFloor.earliest_lawful_cut,
            })
      }
    />
  );

  return (
    <div className="flex flex-col gap-6" data-step="schedule">
      {props.master && (
        <WarningBox
          tone="now"
          data-warning="master-notice"
          sentence={
            <strong>
              {props.occupants === null
                ? t("customers.disconnect.master.noticeBannerUnknown", {
                    defaultValue: "Master account · occupants must be notified",
                  })
                : t("customers.disconnect.master.noticeBanner", {
                    defaultValue: "Master account · {{count}} occupants must be notified",
                    count: props.occupants,
                  })}
            </strong>
          }
        />
      )}

      {props.master ? (
        // The master's notice IS a table array — one row per audience, because
        // `BR-CUS-1098` makes *who is notified* a list rather than a single
        // channel. The cut date sits beside it, as drawn.
        <DisconnectTableArray<DisconnectRecipientRow>
          title={t("customers.disconnect.schedule.notice", { defaultValue: "Notice" })}
          columns={recipientColumns}
          rows={props.draft.recipients}
          rowKey={(row) => row.audience}
          onChange={setRecipients}
          removeLabel={t("customers.disconnect.schedule.removeRecipient", {
            defaultValue: "Remove this recipient",
          })}
          emptyText={t("customers.disconnect.schedule.noRecipients", {
            defaultValue: "Nobody listed. Add a recipient below.",
          })}
          addLabel={t("customers.disconnect.schedule.addRecipient", {
            defaultValue: "+ Add a recipient",
          })}
          onAdd={() =>
            setRecipients([
              ...props.draft.recipients,
              { audience: AUDIENCE_OCCUPANTS, count: props.occupants ?? 0, channel: "", reference: "" },
            ])
          }
          addBlockedReason={
            props.draft.recipients.length < 2
              ? undefined
              : t("customers.disconnect.schedule.bothListed", {
                  defaultValue: "Both recipients are listed.",
                })
          }
          collection="recipients"
        >
          <div className="mt-4 flex justify-end">
            <div className="w-full max-w-[320px]">{cutDate}</div>
          </div>
          {proofMissing && (
            <div className="mt-4">
              <WarningBox
                tone="now"
                data-warning="no-proof"
                sentence={
                  <strong>
                    {t("customers.disconnect.schedule.noOccupantProof", {
                      defaultValue: "Occupants have no proof recorded. You may continue.",
                    })}
                  </strong>
                }
              />
            </div>
          )}
        </DisconnectTableArray>
      ) : (
        <Panel
          as="section"
          title={t("customers.disconnect.schedule.notice", { defaultValue: "Notice" })}
          data-panel="notice"
        >
          {/* `Last sent` is a READ-BACK and not a field — the drawing puts the
              tier and the date at the right-hand end of a full-width row. */}
          <div className="flex items-baseline justify-between gap-4 border border-divider bg-bg px-3 py-2">
            <span className="text-base text-neutral-700">
              {t("customers.disconnect.schedule.lastSent", { defaultValue: "Last sent" })}
            </span>
            <span className="text-base font-semibold text-neutral-900" data-last-sent="">
              {lastSent === null
                ? t("customers.disconnect.schedule.noneSent", { defaultValue: "None sent" })
                : `${lastSent.tier ?? ""} · ${lastSent.issued_on}`}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <SelectField
              id="disconnect-proof-channel"
              label={t("customers.disconnect.schedule.servedBy", {
                defaultValue: "How it was served",
              })}
              value={props.draft.proof.channel}
              placeholder={t("customers.disconnect.schedule.pickChannel", {
                defaultValue: "Choose",
              })}
              onChange={(value) => props.onPatchProof({ channel: value })}
              // ⚠ `PROOF_CHANNELS`, not `SERVICE_CHANNELS` — the portal is a
              // SEND and never a PROOF, and `record_proof_of_service` refuses
              // it by name. Reading one list for both is how a screen offers a
              // clerk an option the server will refuse.
              options={PROOF_CHANNELS.map((channel) => ({
                value: channel.code,
                label: t(`customers.disconnect.channel.${channel.code}`, {
                  defaultValue: channel.en,
                }),
              }))}
            />
            <TextField
              id="disconnect-proof-reference"
              label={t("customers.disconnect.schedule.proofReference", {
                defaultValue: "Proof reference",
              })}
              value={props.draft.proof.reference}
              onChange={(value) => props.onPatchProof({ reference: value })}
            />
            {cutDate}
          </div>
          {/* `servedOn` is REQUIRED by the server and is drawn NOWHERE. A
              certified item is posted on one day and signed for on another, so
              copying one date into both would manufacture a legal date. It is
              asked for only once the clerk has started a proof, which is when
              it becomes the thing that would refuse the write. */}
          {props.draft.proof.channel !== "" && (
            <div className="mt-4 max-w-[320px]">
              <DatePickerField
                id="disconnect-proof-served-on"
                label={t("customers.disconnect.schedule.servedOn", {
                  defaultValue: "Served on",
                })}
                value={props.draft.proof.servedOn}
                onChange={(value) => props.onPatchProof({ servedOn: value })}
                required
                dateFormat={props.dateFormat}
              />
            </div>
          )}
          {proofMissing && (
            <div className="mt-4">
              {/* `BR-CUS-1099` — two short sentences, no explanation. */}
              <WarningBox
                tone="now"
                data-warning="no-proof"
                sentence={
                  <strong>
                    {t("customers.disconnect.schedule.noProof", {
                      defaultValue: "No proof recorded yet. You may continue.",
                    })}
                  </strong>
                }
              />
            </div>
          )}
        </Panel>
      )}

      <DisconnectTableArray<DisconnectVisitRow>
        title={t("customers.disconnect.schedule.whoGoes", { defaultValue: "Who goes" })}
        fact={t("customers.disconnect.schedule.nothingUntil", {
          defaultValue: "Nothing is cut until then",
        })}
        columns={visitColumns}
        rows={props.draft.visits}
        rowKey={(row, index) => `${row.point}-${index}`}
        onChange={setVisits}
        removeLabel={t("customers.disconnect.schedule.removePoint", {
          defaultValue: "Remove this service point",
        })}
        emptyText={t("customers.disconnect.schedule.noPoints", {
          defaultValue: "No service point listed. Add one below.",
        })}
        addLabel={t("customers.disconnect.schedule.addPoint", {
          defaultValue: "+ Add a service point",
        })}
        onAdd={() =>
          setVisits([
            ...props.draft.visits,
            { point: "", label: "", meter: "", visit: "", instruction: "", workOrder: "" },
          ])
        }
        addFact={t("customers.disconnect.schedule.willRaise", {
          defaultValue: "{{count}} work orders will be raised",
          count: workOrderCount(props.draft),
        })}
        collection="visits"
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 · `Step3Schedule.png` ·
//         `MasterStep3.png` · blueprint p138 · **BR-CUS-1099** ·
//         **BR-CUS-1098** · BR-CUS-100 · BR-CUS-039 · `OQ-CUS-1810` ·
//         BR-SHL-025 · B14 rules 20, 21, 31, 32, 33, 42, 43, 44
// generated: 2026-09-25 by lane WIZARD
// exceptions:
//   E1 ⛔ **`assert_service_proved` STILL REFUSES A SCHEDULE WITH NO PROOF**
//      (`cut_on_unrecorded_service`, `DEF-CUS-6736`). `BR-CUS-1099` is
//      CONFIRMED and unwired; the backend half is lane CUTPATH's. This step
//      warns and does not block, which is its half. REPORTED.
//   E1 ⛔ **NOTHING RAISES A WORK ORDER** — `from_flows.FLOW_KINDS` has no
//      debt-shaped door and `propose()` refuses anything else by name. The
//      control is disabled with its reason (§3). REPORTED.
//   E3 **`servedOn` is asked for only once a channel is chosen.** It is
//      required by the server and drawn nowhere; asking for it on an untouched
//      form would add a required field to a step `BR-CUS-1099` has just made
//      optional.
//   E3 **the master's `Notice` is a TABLE and the regular's is a FORM.** Both
//      are drawn that way, and `BR-CUS-1098` is why: *who is notified* is a
//      list once a building is being cut.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
