// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CWP-3925 (six doors shut over live screens) · DEF-CWP-3959 (a
//          card greyed over a screen that had been live 32 hours) ·
//          DEF-CWP-3962 (the bills list held *Pay* after Pay now shipped) ·
//          DEF-CWP-3824 (a disabled CTA over a served endpoint) ·
//          DEF-CWP-3988 (ten drawn screens with no address — the holds that
//          point at them are honest TODAY and are the ones that rot next)
// Rules:   CLAUDE.md hard-won law 2, mirror clause (*"when you write a hold,
//          write the test that fires when the hold expires, in the same
//          commit"*) · CR-068 R3 (a control is held until its screen lands) ·
//          B14 rule 33 (a refusal is five or six words) · BR-CWP-056
// Tests:   10-scripts/gates/g103_holds_cannot_rot.py (the merge gate) ·
//          06-backend/tests/test_cwp_holds_expire.py (the errand cards' own)
// Impacts: every file that draws a HeldButton, a held RowAction or a held
//          DataTable empty-state CTA
// ───────────────────────────────────────────────────────
//
// EVERY HOLD IN THE CUSTOMER PORTAL, AND WHAT WOULD RELEASE IT.
//
// A hold is a rule with a CLOCK in it. It is correct on the day it is written
// and it rots silently on the day the thing it was waiting for arrives,
// because landing a screen and releasing the control that points at it are two
// acts and only the first one feels like the work. That has now happened four
// times in one week on this one product — the front page's six shut doors, the
// requests hub's *Something else* (grey for 32 hours over a screen headed ASK
// US SOMETHING), the bills list's *Pay* (held over `CWP-038` for days after it
// shipped), and Settings' *New answer* (disabled over `create_answer`, which is
// routed, audited and working).
//
// **Nothing in this repo could see any of them.** `tsc` passes, 42 portal test
// files and 391 cases pass, `G13` passes — it asks whether a prop is PASSED,
// never whether a refusal is still TRUE — and `G100` passes, because it asks
// whether anything POINTS at a screen and credits a held control as a pointer.
// The one check that existed, `tests/test_cwp_holds_expire.py`, covers the
// three errand cards and nothing else. This file is that check generalised: it
// writes down, as DATA, the expiry condition of every hold the portal draws, so
// that `g103_holds_cannot_rot.py` can fail the merge on the day one comes due.
//
// ⚠ **THE REGISTER IS KEYED BY THE REASON'S i18n KEY, NOT BY THE CALL SITE.**
// The reason is the thing that makes a claim about the world — *"arrives later
// this year"*, *"is not ready yet"* — and it is the thing that becomes false.
// Keying by call site would have needed an edit in five lanes' files at once,
// which is hard-won law 11's mechanism two with extra steps; keying by reason
// key needs one file, and a lane that adds a hold has to add one row here or
// G103 fails its merge.
//
// **The naming convention the gate scans for** is the one the catalogues
// already follow without exception: a hold's reason key ends in `Held` or
// contains `.held.`. All 32 live holds match it. A key that does not is
// invisible to the gate, which is a false negative stated here rather than
// discovered later (hard-won law 1).

/** What would make a hold false — and whether anything mechanical can see it. */
export type HoldExpiry =
  /** Released when this `CWP-###` gains a row in `PORTAL_SCREENS`. WATCHED. */
  | { readonly kind: "screen"; readonly screen: string; readonly note: string }
  /**
   * Released when this Python symbol is defined anywhere under
   * `06-backend/apps/`. WATCHED.
   *
   * ⚠ **A NAME THE IMPLEMENTER MIGHT NOT USE IS A FALSE NEGATIVE**, so a row
   * only ever names a symbol that is either (a) already defined — in which
   * case the hold has ALREADY rotted and G103 is red today — or (b) the exact
   * name the seam/selector convention would force. Where neither is true the
   * row is `unwatched` and says so, rather than pretending to a check.
   */
  | { readonly kind: "endpoint"; readonly symbol: string; readonly note: string }
  /** The SERVER decides this per account and re-decides on every draw. Cannot rot. */
  | { readonly kind: "server"; readonly note: string }
  /** The person has not finished the form, or the list is not in the right order. Cannot rot. */
  | { readonly kind: "form"; readonly note: string }
  /** A ruling says this does not open here at all. Only a CR reverses it. */
  | { readonly kind: "policy"; readonly note: string }
  /** Not a refusal — a statement of fact about this account, wearing the same component. */
  | { readonly kind: "fact"; readonly note: string }
  /**
   * A deferral nothing mechanical can see — a wave order, a capability with no
   * id and no symbol. **THE WEAKER KIND**, and the same admission
   * `ERRAND_HELD_UNTIL`'s `null` makes. G103 COUNTS these and prints the count,
   * so the number of promises nobody is keeping is visible rather than
   * discovered by a customer.
   */
  | { readonly kind: "unwatched"; readonly note: string };

export const PORTAL_HOLDS: Readonly<Record<string, HoldExpiry>> = {
  // ── Held on a SCREEN that does not exist yet ────────────────────────────
  // ⚠ **`portal.readings.sendReadingHeld` STOOD HERE, `kind: "screen"` over
  // `CWP-035`, AND IT EXPIRED THE WAY THIS FILE PROMISES (2026-10-17,
  // `DEF-CWP-10175`).** The screen landed; the Readings head action is a
  // live link now and the key is out of all eleven catalogues.
  "portal.held.card": {
    kind: "unwatched",
    note: "CWP-001's `what_things_cost` card. CR-068 §9 allocates NO id for a tariff page, so there is no screen to watch — and `check_my_area` must not get one until R9 is reversed. FrontPage.test.tsx pins CARD_ROUTE against PORTAL_SCREENS, which is the half that can be checked.",
  },

  // ⚠ **`settings.portalHelp.addHeld` STOOD HERE, `kind: "endpoint"`, over
  // `create_answer` — and it is the row G103 was RED on when it landed
  // (`DEF-CWP-3824`).** *New answer* is a live control now, the hold is gone
  // and its copy is out of all eleven catalogues. The row is remembered here
  // rather than simply deleted because it is the worked example of what the
  // `endpoint` kind is FOR: a hold that says a capability is not built, over
  // one the back end has served since `2.138.0`.

  // ⚠ **TWO ROWS STOOD HERE AND BOTH WERE RELEASED BY `CR-085` WAVE 3
  // (`CPB-14`, `CPB-15`, `CPB-20`), 2026-09-08.** They are remembered rather
  // than silently deleted because they are the worked example of what
  // `unwatched` COSTS — the kind of hold this gate cannot see.
  //
  //   "portal.documents.downloadHeld" — CWP-031's *Download a year*. Its note
  //   read *"No file-serving path exists in apps/portal at all"*. That was true
  //   when it was written and stopped being true the day `US-CWP-034` shipped
  //   `bill_document_pdf` on the portal edge — behind the portal session,
  //   behind the same `download` permission, streaming out of the same store.
  //   Nobody re-read the note, and a control that had had a route for days went
  //   on saying *Downloads are not ready yet*.
  //
  //   "portal.money.receiptHeld" — CWP-041's per-payment receipt, *"same shape
  //   as the documents download"*. Same store, same answer.
  //
  // **Neither could have gone red.** `unwatched` is the kind that admits there
  // is nothing mechanical to watch, and its own count is printed for exactly
  // this reason. What found these two was somebody opening the screen and
  // asking what the customer came for — which is the walkthrough's job and
  // never a gate's (G103's own WHAT IT CANNOT SEE).
  //
  // ── Held on a capability with no id and no symbol — the weaker kind ─────
  // ⚠ **RESTORED 2026-09-06 — THIS ROW WAS REMOVED BY A SIBLING'S COMMIT
  // SIX HOURS AFTER IT LANDED (`DEF-CWP-4187`), AND G103 WENT RED AGAIN ON
  // EXACTLY THE FAULT IT HAD JUST BEEN FIXED FOR.** `4721f304` added it to
  // close `DEF-CWP-4129` — the gate against rotting holds, itself unread for
  // 165 commits. `516f55b5` then wrote a whole-file copy of `holds.ts` that
  // predated it, which subtracts by omission: the file count was right, the
  // author's own hunks were present, and the deleted row is not in that
  // commit's diff at all because it is missing from the tree the diff is
  // taken against (hard-won law 11, `DEF-1706`). Restored byte for byte
  // from `4721f304`; the refusal is still true.
  "portal.quickPay.receiptEmailHeld": {
    kind: "unwatched",
    note: "CWP-046's guest quick-pay receipt EMAIL — the sibling of the two rows above, and the row whose absence kept G103 red for 165 commits (DEF-CWP-4129). The refusal is TRUE today and the back end says so honestly rather than faking a send: gateway.py note E3, 2026-09-05, records that the guest's typed receipt address goes nowhere and `receipt_sent` reports false. Unwatched rather than `endpoint` because no send path for a guest payment exists in apps/notifications at all, so there is no symbol this row could name without inventing one — and this file's own rule is that a row names a symbol only where it is already defined or the convention forces the name, and says `unwatched` otherwise rather than pretending to a check. QuickPayCheck.tsx's comment beside the hold claims *the day the product can send a receipt the suite goes red and names this block*; THIS ROW is that test, and until now the comment was a claim with nothing under it (hard-won law 1).",
  },
  "portal.money.exportHeld": {
    kind: "unwatched",
    note: "CWP-041's CSV export. A download, not a screen.",
  },
  //   "portal.yourPlan.agreementHeld" — CWP-043's signed agreement, RELEASED
  //   by `CR-085` `CPB-14` (2026-09-08). The third row of the same shape: the
  //   store has kept plan agreements all along, `CPB-03` released the OFFER
  //   screen's copy of this hold a wave earlier, and this one stayed because
  //   releasing a control and releasing its twin are two acts. Its refusal is
  //   now `portal.documents.cannotOpen`, drawn only where the store actually
  //   has no copy — a `fact`, answered on every draw.
  "portal.quickPay.receiptHeld": {
    kind: "unwatched",
    note: "CWP-004's receipt download. A document.",
  },
  "portal.quickPay.emailHeld": {
    kind: "unwatched",
    note: "CWP-004's *email me the receipt*. Email activates in W6 by wave order (10-execution-plan.md §0 row 23) — a date in a plan, which no gate reads.",
  },
  "portal.sent.textMeHeld": {
    kind: "unwatched",
    note: "CWP-007's *text me updates*. ⚠ SMS ITSELF IS LIVE FROM 2026-10-29 (CR-198-BRC10, one shared platform Twilio account) — this note said *SMS activates in W8* until then. What still holds the control is that a GUEST reporter's number has no write path to subscribe it to an outage's updates (no endpoint, no consent record for a non-customer), which SMS going live does not provide. Filed rather than released.",
  },
  "portal.autopay.turnOffHeld": {
    kind: "unwatched",
    note: "CWP-040's *Turn autopay off* — *Ring us to stop autopay*. ⚠ **THE RULING ARRIVED AND THE HOLD DID NOT MOVE, WHICH IS THE POINT OF THIS ROW SAYING SO.** OQ-CWP-1568 is CLOSED (2026-09-11): a signed-in customer MAY turn autopay off — PO verbatim, *\"a). A customer who has to ring to accept a payment plan often doesn't ring. These are the people you've twice told me to prioritise.\"* **So what holds this control is no longer PERMISSION; it is that nothing can perform the write.** Measured 2026-09-11: apps/portal/api.py serves autopay as `GET accounts/{id}/autopay` and nothing else, and write_points.py has no row for it — and that file says in its own words that adding one *\"is a ruling and not an edit\"*, with G81 failing the build until one is recorded. The ruling settled permission and explicitly left the DESIGN open: the audit row every money action must write (CLAUDE.md hard rule 7), whether the change is reversible, and the write-point count. ⚠ The customer-facing sentence *Ring us to stop autopay* stays TRUE and stays five words (B14 rule 33) — ringing is still the only way off. Unwatched rather than `endpoint` because the stop path has no name yet, and naming one here would be this file inventing the symbol it claims to watch. What releases it is a WAVE now, not a ruling.",
  },
  "portal.levelPay.joinHeld": {
    kind: "unwatched",
    note: "CWP-044's *join budget billing* — *Ring us to join budget billing*. ⚠ OQ-CWP-1568 IS CLOSED (2026-09-11): the PO ruled that a signed-in customer MAY join budget billing, so the question that used to hold this row is ANSWERED and this note used to say it was open. **Permission is not a write path and the control stays held.** Enrolling writes account_budget_status; BR-CWP-001 allows the portal rows of exactly six kinds and budget enrolment is none of them; write_points.py says adding one 'is a ruling and not an edit' and G81 fails the build until a row is recorded. Still to decide, and all three are OURS rather than the PO's: the seventh write point, the audit_log row the write must leave (CLAUDE.md hard rule 7) and whether an enrolment can be undone. Still unwatched, by this file's own rule: no symbol exists and the one it would take is not forced by any convention, so naming one would be inventing it. ⚠ The reason a customer reads is the catalogue's own six words; the server's join_held_reason is the literal string 'OQ-CWP-1568' and must never reach a screen (B14 rule 31).",
  },
  "portal.planOffer.actionsHeld": {
    kind: "unwatched",
    note: "CWP-063's accept / different terms / decline — *Ring us to answer this offer*. ⚠ OQ-CWP-1568 IS CLOSED (2026-09-11): the PO ruled YES to all three, in the words 'a customer who has to ring to accept a payment plan often doesn't ring'. This note used to say the question was open. **The controls stay held anyway, because permission is not an endpoint.** apps/portal serves plan_offer as a READ and there is no answer path; a plan signature is a seventh write kind under BR-CWP-001 and G81 fails the build until write_points.py carries a row for it. Still to decide, ours not the PO's: the write point, the audit_log row each of the three writes must leave (CLAUDE.md hard rule 7), and whether a DECLINE can be reversed — which matters most, because declining is the one of the three a frightened person does by accident. Still unwatched: no symbol exists and none is forced. ⚠ Both rows named OQ-CWP-1565 until 2026-09-06 — an id that was never issued (DEF-CWP-4139), so the question that would release four controls could never be found from them. ⚠ AND THE COUNT IN THE REGISTER WAS WRONG TOO: the ruling releases FIVE controls on THREE screens, the third being CWP-040's turn-autopay-off row above — which the autopay lane has already corrected, and whose wording is worth reading beside this one: it reaches the same conclusion from the same ruling, independently.",
  },
  "portal.methods.editHeld": {
    kind: "unwatched",
    note: "CWP-039's row edit. Adding and removing a method are served; changing one in place is not, and the seam name it would take is not settled.",
  },

  // ── The SERVER decides, per account, on every draw — cannot rot ─────────
  "portal.payNow.held.*": {
    kind: "server",
    note: "CWP-038. Six codes — cash only, expired card, no provider, no saved method, provider cannot charge, this login may not pay. Every one is re-answered by the server each time the screen draws.",
  },
  "portal.autopay.held.*": {
    // ⚠ **MOVED FROM `server` TO `unwatched` ON 2026-09-06 (`DEF-CWP-4142`),
    // AND THE RECLASSIFICATION IS THE WHOLE POINT.** It read *"Bounced
    // payments and cash-only, both per account"* — which describes only WHICH
    // of two reason strings is sent. What decides whether the control is held
    // at all is `apps/payments/autopay.py`'s `"available": False`, a literal
    // with no condition beside it and a comment reading *FALSE TODAY AND FALSE
    // UNTIL RAILS*. So the true expiry is a CHARGING PATH LANDING, not a fact
    // about an account — and a `server` row claims a hold that CANNOT rot,
    // which would have left this one refusing over a live path with G103
    // green. No symbol is named because the drafting path has none yet.
    kind: "unwatched",
    note: "CWP-040's *Turn autopay on*. Held until something in this product can DRAFT a payment against a stored instrument — `BR-PAY-015`'s intent exists and nothing consumes it (`intent_recording_has_no_caller`). The cash-only and bounce branches choose WHICH sentence is shown; they do not decide whether the control is live.",
  },
  "portal.fees.held.*": {
    // ⚠ **MOVED FROM `server` TO `unwatched` ON 2026-09-06 (`DEF-CWP-4142`).**
    // The old note said `no_fee_payment_path` was *"the tenant's own
    // configuration"*. It is not configuration of any kind:
    // `apps/portal/paying.py` returns `"available": False` and this one reason
    // on BOTH of its return paths, with no condition anywhere in the file.
    kind: "unwatched",
    note: "CWP-050's *Pay $335.00*. A fee is a `service_request_fees` QUOTE that never posts to the ledger, `collect_fee` is a counter action gated to Admin or Billing Clerk, and `write_points.py`'s `payment` row carries `function=None` for it. Released when the portal gains a fee-payment write point; that function has no settled name, so no symbol can be watched honestly.",
  },
  "portal.requests.held.*": {
    kind: "server",
    note: "CWP-046's errand cards. ⚠ ALREADY WATCHED, and by the check this file generalises: the server's ERRAND_HELD_UNTIL names the releasing screen per card and tests/test_cwp_holds_expire.py reads it against PORTAL_SCREENS. DEF-CWP-3959 is the hold that rotted before it existed.",
  },
  "portal.methods.autopayBlocked.*": {
    kind: "server",
    note: "CWP-039's autopay row — bounced, cash only, or a code this build has not heard of.",
  },

  // ── The person has not finished — cannot rot ────────────────────────────
  "portal.askPlan.askHeld": { kind: "form", note: "CWP-042 — the dates are empty." },
  "portal.dispute.checkHeld": { kind: "form", note: "CWP-055 — both boxes are empty." },
  "portal.sendReading.sendHeld": { kind: "form", note: "CWP-035 — the number on the dial is empty (DEF-CWP-10175)." },
  // CWP-035 · US-CWP-042 TC-11 — consumer upload is a SIGNED deferral (PO 2026-08-08,
  // DF-4; DEF-CWP-3611). The picker renders its sentence and no file input; only
  // a re-sign of the deferral releases it.
  "portal.sendReading.photoHeld": {
    kind: "policy",
    note: "CWP-035 — a photo of the meter. Consumer upload is DF-4, a signed deferral; a re-sign releases it, nothing else.",
  },
  "portal.dispute.sendHeld": { kind: "form", note: "CWP-055 — both boxes are empty." },
  "portal.question.sendHeld": { kind: "form", note: "CWP-054 — no topic chosen, nothing written." },
  "portal.request.sendNoteHeld": { kind: "form", note: "CWP-051 — the note is empty." },
  "portal.startService.checkHeld": { kind: "form", note: "CWP-008 — no address typed." },
  // ⊕ **START SERVICE's SIX STEP-GATES (`DEF-CWP-4877`), REGISTERED 2026-10-02
  // WITH THE SIXTH (`DEF-CWP-9163`, the mailing address).** Each holds a
  // `Continue →` or *Send* over a box the applicant has not filled, and is
  // re-decided on every keystroke by `unfinished()` in `ApplyForService.tsx` —
  // the browser's copy of `applications.missing_before_submit`. The first five
  // were drawn with no row here, so G103 was red on them from `DEF-CWP-4877`.
  "portal.apply.held.services": { kind: "form", note: "CWP-047 step 2 — no service ticked (an address we do not hold)." },
  "portal.apply.held.startDate": { kind: "form", note: "CWP-047 step 2 — no start date." },
  "portal.apply.held.name": { kind: "form", note: "CWP-047 step 3 — first or last name empty." },
  "portal.apply.held.companyName": { kind: "form", note: "CWP-047 step 3 — a business with no company name." },
  "portal.apply.held.taxId": { kind: "form", note: "CWP-047 step 3 — a business with no tax ID." },
  "portal.apply.held.contact": { kind: "form", note: "CWP-047 step 3 — email or mobile empty." },
  "portal.apply.held.mailing": {
    kind: "form",
    note: "CWP-047 step 3 — Same as the service address unticked, and the mailing address not whole (DEF-CWP-9163).",
  },
  "portal.stopRestart.commitHeld": { kind: "form", note: "CWP-052 — no stop date given." },
  "portal.stopRestart.phoneHeld": {
    kind: "form",
    // ⚠ **THIS ONE IS NOT A DEFERRAL, IT IS A BOX WITH NOTHING IN IT** — and
    // that distinction is why it is `form` rather than `unwatched`. It cannot
    // rot, because it is re-decided on every keystroke. `create_from_portal`
    // REQUIRES `applicant_phone` (*"a promise to ring needs a way to ring"*),
    // and until CR-085 the screen sent none at all: every press of *Request
    // this ✓* answered 422, on a route that had no door in the portal, so
    // nobody had ever reached it.
    note: "CWP-052 — the phone box is empty, and the server refuses a request with no way to ring back.",
  },
  "settings.portalTips.reorderHeld": {
    kind: "form",
    note: "CWP-073 — a row can only be moved while the list is sorted by order and unfiltered. A statement about the list's state, not about what is built.",
  },

  // ── A ruling says this does not open here ───────────────────────────────
  "portal.yourAccount.sendCertificateHeld": {
    kind: "policy",
    note: "CWP-065 — *Post or bring it in*. BR-CWP-089: the portal accepts NO upload and every protection needs a person and a document, so the route ends at the counter by ruling. YourAccount.dom.test.tsx carries the case that fires if the deferral is lifted.",
  },
  "portal.question.photoHeld": {
    kind: "policy",
    note: "CWP-054 — a signed deferral, and there is no file input on the screen at all.",
  },
  "portal.report.photoHeldReason": {
    kind: "policy",
    note: "CWP-006 — the same signed deferral, one screen over. ⚠ The catalogues also carry `portal.report.photoHeld`, which NOTHING draws: the screen reads `photoHeldReason`. G103 names an unused row for exactly this reason — a released or renamed hold whose copy is still being carried in eleven languages.",
  },
  // ⚠ **`portal.apply.proofHeld` WAS HERE AND IS RELEASED — `CR-158-BRC10`,
  // PO 2026-10-01.** CWP-047's proof-of-identity box was held under `DF-4`
  // (*consumer upload portal = v2*) and its note said *"Released by the B9
  // re-sign, not by a screen landing"*. That re-sign arrived: *"we need to now
  // accept the document from portal"*, for the new-service request ONLY. The
  // box is the live `ApplicationDocuments` drop zone, the key is retired from
  // all eleven catalogues, and `CheckAndSend.dom.test.tsx` carries the case
  // that asserts the held shape is GONE. CWP-006 and CWP-054 above keep `DF-4`.
  "portal.apply.saveLaterHeld": {
    kind: "policy",
    note: "CWP-047 — *Already saved as you type.* The control exists to say a save is unnecessary, which is permanently true of a draft-link form.",
  },

  // ── Not a refusal at all — a fact wearing the same component ────────────
  "portal.finalBill.queryHeld": {
    kind: "fact",
    note: "CWP-032 — this branch draws ONLY when the final bill carries no number, and `/bills//dispute` opens nothing. When it has one the control is a live ErrandLink to CWP-055. Answered by the data every time it draws.",
  },
  "portal.documents.yearNothingKeptHeld": {
    kind: "fact",
    note: "CWP-031's *Download a year*, held ONLY while this account has no kept copy of anything. It replaced `portal.documents.downloadHeld`, which was `unwatched` and rotted silently (CR-085 CPB-15). This one is a `fact` and cannot: the rows on the screen answer it on every draw, so the day a copy is kept the control is live in the same render. That is the difference between a refusal about the WORLD and a refusal about this account.",
  },
  "portal.finalBill.depositHeld": { kind: "fact", note: "CWP-032 — a deposit line's label." },
  "portal.finalBill.depositHeldSince": {
    kind: "fact",
    note: "CWP-032 — the same label when the date the deposit was taken is known.",
  },
  "portal.payNow.heldNoAmount": {
    kind: "form",
    note: "CWP-038 — no amount chosen yet. ⚠ Its sibling `heldNoPreview` was DELETED (DEF-CWP-3970) and survives only in PayNow.tsx's prose explaining why; G103 strips comments before scanning, so that sentence stays safe to keep.",
  },
  "portal.yourAccount.depositHeld": { kind: "fact", note: "CWP-065 — what is being held, and since when." },
};
