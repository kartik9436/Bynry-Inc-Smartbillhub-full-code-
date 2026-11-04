# CR-132-BRC07 — New World / Logos reads our receipts

**Raised:** 2026-09-22, by the Product Owner, for a municipal utility going live on Tyler
Technologies' New World ERP (Logos).
**Branch block:** `BRC07` (`CR-130`–`CR-134`), `claude/laughing-thompson-kpmwih`.
**Version:** `2.327.0`.
**Classification:** **CHANGE** — a new partner integration nobody had asked for before. Not a
defect: the product does what it was asked to do, and this is a new thing to ask of it.

---

## 0 · What arrived, in the requester's words

> *"i think we shoudl create seperate enpoint - you can se the same components that you use, dont
> write completely new code - what way we can keep it sepearet"*

> *"we need seperate endpoint if we deicde only for payemnt and not for ledge"*

and, through the build, four more rulings recorded in `02-decision-log.md` of the same date:

> *"please send receipt even if it is not balance"*

> *"we send ACH, Moenry Order and Lockbox - as mapping from our side and wil ask them to map it at
> their end"*

> *"we are mapping gL code to various utility services and all cahrge codes so we will ahve a gl
> code"* · *"okay leave them empty and do rest"*

---

## 1 · What is being reversed

**Nothing signed.** No ❄️ FROZEN B4/B5 figure is touched — this change computes no money, it
projects money somebody else already computed.

**One thing this lane's own brief said is reversed by the PO**, and it is recorded rather than
quietly applied: the brief said *refuse to emit a receipt that does not balance*. **The PO ruled
the opposite.** A refused receipt is money that silently never reaches the City's books; an
unbalanced one is money that arrives wrong and can be found and fixed.

---

## 2 · Impact across the surfaces

| surface | impact |
|---|---|
| API | **ONE new address** — `GET /api/partner/v1/receipts`. `/api/partner/v1/ledger` **reused unchanged**; not one line moved. |
| schema | `payments.origin` + `payments.origin_is_derived` + `ix_payments_origin` (`payments/0029`). No other table. |
| connectors | `erp_newworld`, one manifest file. `CONNECTOR_COUNT` 30 → 31. No migration, no screen code. |
| screens | **none.** The connection card and its two API rows are drawn from the manifest, because a manifest is data (`BR-INT-037`). |
| other partners | **none.** Four ERP manifests share the route table and no existing payload changes by a byte. |
| demo fixture | none. |
| open questions | one opened (`OQ-INT-12574`, New World's validation set); three closed by PO answer the same day. |
| defects | two filed: `DEF-INT-6161`, `DEF-INT-6162`. |

---

## 3 · What was already built that this makes wrong

**Nothing.** This is additive. The one thing it changes about existing behaviour is that
`payments.origin` is now written at creation by four call sites that previously wrote nothing
there — and the column did not exist before, so no reader can have depended on it.

⚠ **Lanes running now:** six siblings on rating, premises, routes and the chart of accounts. **No
file is shared with any of them.** The registers are, and are appended to rather than rewritten.

---

## 4 · The shape of the answer

**Separate PROJECTION, shared everything else.** The PO's *"dont write completely new code"* is
honoured by what this change did NOT write:

* key auth, tenant-from-key, the access log and the rate window — **nothing written**; the door is
  `partner_api._admit`'s, and the address is registered in `PARTNER_ROUTES` so it cannot exist
  without the key ─► tenant ─► RLS arrow.
* the GL account — **`seams/ledger.account_code`**, the same resolution Aclarian's ledger rows go
  through. A GL rule changes in one place, and a test asserts the projection reads no chart.
* the payment facts — `seams/payments`, extended by one `origin` filter argument rather than
  copied.
* the XML — `codecs`' own conventions and fixture discipline (`fixtures/newworld/`).
* the tender and bill-type vocabularies — **config in `mappings.py`**, overridable per tenant by an
  ordinary mapping row, so New World's spellings change without a release.

**What is genuinely new: one view, one manifest, one projection module, one migration.**

---

## 5 · Version and rollback

`2.327.0` — a CHANGE level, allocated against the remote at push time.

**Rollback:** `migrate payments 0028` drops both columns and the index; the migration's reverse
clears only rows it stamped and never an observed value. Reverting the code removes one address and
one connector card. `/api/partner/v1/ledger` is unaffected by construction.

---

## 6 · Still open with New World's team

**`OQ-INT-12574`** — will they add `ACH`, `Money order` and `Lockbox` to their *Other Payment Type*
validation set, and with what spelling? **Nothing is blocked**: receipts are sent meanwhile and a
rejection is their control working, which is this change's whole posture.

## 7 · Deliberately not built

* **The four card fields.** Not built and switched off — **NOT BUILT**. `G130` keeps it that way.
* **Remainder assignment for a rounding residue.** Measured at **zero occurrences on the real
  path** (7 receipts, 7 balanced); the ruling is *send it*, and a fix for a thing that does not
  happen is a thing to maintain.
* **A schedule.** Whether New World calls on their own timetable or we deliver a file is a
  conversation with their team. **The API is built so either works**, which is the point of the
  approach.
