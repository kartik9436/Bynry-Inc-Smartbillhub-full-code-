# A5 — Status Values & State Machines

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Every status; transition tables; money-affecting transitions.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


**Account:** Active, Pending activation, Pending (excluded), Marked disconnect, Closed/Vacant, Excluded. `UNKNOWN — full lifecycle + who moves each.`
**Meter Read:** OK, High, Low, Missing, Estimated (1st/2nd consecutive), Days-threshold, Meter-factor flagged.
- Missing → Estimated (auto-estimate) | → Field visit | → Skip cycle
- Estimated → trued-up on next real read (reversible on real read).
**Bill / Invoice:** Draft (in run), Paid, (implied) Issued/Open, Void `INFERRED`. `UNKNOWN — issued vs open vs overdue labels; the Bills tab shows "Paid" and billing run shows drafts.`
- Draft → Issued (generate bill) → Paid (payment applied) | → Corrected (correction process) | → Void `INFERRED`.
**Payment:** Cleared, Processing, Failed, Posted (credit/adjustment). Reversed `INFERRED via Reverse action`.
- Processing → Cleared | Failed. Failed → Retry → Processing. Cleared → Reversed (Reverse modal, reason required; restores bill balance).
**Deposit Batch:** In transit, Unmatched, Matched, Reconciled.
- In transit → Matched (bank posts) | Unmatched (diff). Unmatched → Resolve → Matched → Reconciled (lockable). Reconciled reversible via "Unreconcile".
**Tax filing:** Accruing, Due soon, (Overdue), Filed.
- Accruing → Due soon → Filed. → Overdue if past due.
**Payment Plan:** proposed → agreement sent (e-sign) → Active → Closed (final installment). `UNKNOWN — default/broken-plan status.`
**Subscription:** trial (14-day) → active. `UNKNOWN — past_due/canceled states.`

Money-affecting transitions to lock down: **issue bill, void, credit, adjust, refund, write-off, payment reverse, NSF bounce.** All require role gating (Doc 4) and audit entries (Doc 6). `UNKNOWN — reversibility windows and whether voids are hard-delete or reversing entries (should be reversing).`

Orphan statuses: bill "Issued/Open" appears implied but no explicit control to enter it separately from generate — confirm.

---


## Addendum — Asset lifecycle (2026-08-07 r4)
Statuses: **inventory, active, needs_repair, in_repair, retired**.
Transitions: inventory →(assign/install)→ active · active →(flag)→ needs_repair →(start)→ in_repair →(fix)→ active · any →(retire, reason+date)→ retired (terminal). Delete allowed only from inventory when never referenced by a read/bill; otherwise retire.

## Addendum — invoice status vocabulary settled (2026-08-08, from B2)
The `UNKNOWN` on bill labels above is resolved by the B2 enum: `invoice_status = draft | issued | paid | void | corrected`.
Draft → Issued (generate) → Paid | Void (reversing entry, assumed — O-4) | Corrected (credit note/rebill). "Open/Overdue" are derived display states (issued + due-date math), not stored statuses.

## Addendum — service billing basis (2026-09-02, PO ruling; `BR-TEN-1180`)
`tenant_services.billing_basis = metered | share | capacity`. **Contract-level: these three
strings are what the API accepts and serves**, on `GET`/`PATCH /settings/services/{code}`, under
the field name `billing_basis`. There is no fourth value and no NULL — the column carries a
not-null default of `metered`.

**It is a VOCABULARY, not a state machine, and it has no transitions to draw**: any value may
become any other, at any time, on S8 → Services & UoM. The one thing that follows a change is
`BR-TEN-810`'s forward-only rule — issued bills, their lines, the payments against them and the
journal entries do not move, and the new basis takes effect on the next bill not yet priced.

What each value means to the bill run:
* `metered` — a register is read; the billable quantity is read × the meter multiplier.
* `share` — a percentage of another service's money (`BR-RAT-015`: sewer is a percentage of the
  water usage charge). No register, no count, **and no unit of its own** — the one value whose
  services legitimately carry a null primary UoM.
* `capacity` — the capacity standing on the unit (`BR-RAT-090`): carts, ERUs, Mbps, and kW for
  battery and solar. The size class selects the rate. **It is a COUNT for the units that come
  in one size and a SUM for the ones that do not** — `CR-062` statement (6): three solar
  panels of 2 kW, 4 kW and 8 kW bill as **14 kW**, not as 3.

  ⚠ **THE SUM IS BUILT AS OF 2026-09-02 (`CR-062` D1/H2) AND THE SENTENCE ABOVE IS NOW
  DESCRIBING CODE RATHER THAN INTENT.** Until that day `total_capacity()` existed, was
  tested, gave this exact worked example in its own docstring and **had no caller** — the
  bill run read the asset COUNT, so the PO's array billed **3 x $14.00 = $42.00** instead
  of **14 kW x $14.00 = $196.00** (hard-won law 2: built is not wired). What decides which
  arithmetic applies is the SERVICE'S OWN CONFIGURATION and never a list of service names:
  the service's ratified size classes must carry a summable capacity
  (`service_size_classes.capacity_uom_for_service`, which answers `None` for trash, fire
  and every banded service) AND that must be the unit the tariff quotes its price per.
  **Trash and fire still COUNT** — 3 carts x $15.00 = $45.00, and a 6" fire line with two
  2" lines = $84.00 — and B5 `GT-15`'s $40.00 solar, priced per `panel`, is unmoved.
  ⚠ **THAT FIRE EXAMPLE READ *"a 6" line with two hydrants = $110.00"* UNTIL 2026-09-03**,
  when the PO said *"remove private hydrants from list"* and `HYD` left fire's size list —
  a hydrant is an asset, not a utility-service size. The warehouse it described now bills
  **$60.00**, `−$50.00` a month. **Fire's ARITHMETIC did not move an inch**, which is all
  this paragraph is about: the size picks the price, the count multiplies it.

  ⚠ **AND THERE IS A THIRD ARITHMETIC, ADDED 2026-09-02 (`CR-062` D6, PO ruling), BECAUSE
  ONE CAPACITY SERVICE HAS NOTHING STANDING ON THE UNIT TO COUNT OR TO SUM.** The two
  above both read INSTALLED EQUIPMENT — a cart, a panel, a modem, each carrying its own
  size (`BR-AST-500`). **Storm water has no such thing:** an ERU measures hard surface on a
  property and nobody installs one, so the sum was `0` on every unit and the line printed
  **`$0.00`** on a document that footed and printed (`DEF-2388`). PO verbatim: *"In case of
  strom water - we have to take it from Unit - B ⭐ Take the size from the property, not
  from equipment. Storm water becomes the one capacity service whose quantity comes from
  the premises"* — option B of three, **corrected in the same sentence from the property to
  the UNIT**, because a bill is for an account, an account serves a unit, and on the
  premises storm water would be the only line needing to be divided down before it could be
  charged. So the third source is **a capacity RECORDED ON THE UNIT ITSELF**, in
  `service_characteristics` under the key `assessment` with `ERU` in `unit_of_measure`
  (`BR-MET-108`'s shape). **Worked:** a house is **1 ERU x $4.50 = $4.50** a month, an
  apartment block's 6 ERU is **1 ERU on each of its six flats** and so **$27.00** across the
  block, and the demo estate is **59 ERU = $265.50** of assessment (**$270.00** collected — `BR-RAT-101`'s outside-city 1.5x lands on two of those houses, and a surcharge multiplies the price, never the measurement; the estate figure read **54 ERU / $243.00 / $247.50** until 2026-09-02, when `CR-062`'s addendum appended two premises under it — `DEF-2368`). **It is storm water and nothing else**
  — `connections.unit_capacity_key` answers `None` for solar, battery, broadband, trash and
  fire, and a pure case asserts that rather than a sentence claiming it.

⚠ **SUPERSEDES the boolean `tenant_services.metered`** (`BR-RAT-081`, PO 2026-08-20), which is
gone from the database. It survives as a read-only derived property equal to
`billing_basis == "metered"`, so the readers that ask *"is there a register?"* are unchanged. The
reason two values were not enough is sewer: it reads no register AND is not priced by a count, so
neither side of the boolean was true for it, and the false side was already committed to meaning
`BR-RAT-090`'s asset count.
