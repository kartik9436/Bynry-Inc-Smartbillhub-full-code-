# CR-164-BRC10 — New Connection wizard, steps 1 to 5: the PO's screen-by-screen changes

**Raised:** 2026-10-02, by the Product Owner, in chat, as part of the New Connection
programme (decision-log row of 2026-10-02 headed *"NEW CONNECTION — THE PO'S
SCREEN-BY-SCREEN REVIEW BECOMES ONE PROGRAMME"*, commit `56eb54ba9`). That row is the
ruling; nothing it settles is put back to the PO (hard-won law 13).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in
`12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr` answered **164**
against the remote.
**Lane:** NC-C (the five wizard screens, staff side). Siblings: NC-A (`CR-162-BRC10`,
lifecycle, approval, master account by premises type, premises Pending at Create) and
NC-B (`CR-163-BRC10`, the request details tabs). This lane CONSUMES NC-A's statuses and
builds no approval.
**Classification:** MAINTENANCE on a live screen (`22-product-maintenance-process.md`).
Where the screen contradicted a ruling it is filed as a defect (`DEF-CUS-9192`–`9200`);
where the PO asked for something the screen never did it is a change carried here.

## 0 · What arrived, in the requester's words

> *"Q1–Q8 as recommended, go"* · *"Messages: one table with a template dropdown on each
> row - this should be table array"* · *"Step 5 · What Create makes - show lifecycle
> status of all items in this list"*

Q4 DOB in the future or under 18 refused; SSN/DL masked. Q5 customer match within the
tenant: SSN or DL exact = match; name + DOB = possible match; name alone or DOB alone = no
match. Q6 budget billing removed from step 2. Q7 City/State mismatch reason; hide Unit/apt
for apartment complexes. Q8 messages fire on approval (BR-MET-115), language from step 1,
the charges line once.

## 1 · The items, step by step (coordinator's numbering)

| Step | Item | What changes | Record |
|---|---|---|---|
| 1 | 49 | Owner type read from the utility's own owner list, not four hand-typed codes | `DEF-CUS-9192` |
| 1 | C | Date of birth: a future date or an owner under 18 is refused | `DEF-CUS-9193` |
| 1 | D | SSN and driving licence masked | `DEF-CUS-9194` |
| 1 | 10 | Mailing address and Co-applicant collapsible | change |
| 1 | 11 | Customer ID box removed; automatic match within the utility (SSN or DL = match, name + DOB = possible), *Use this customer* / *Not this person*, else *Customer not found. A new customer will be created.* | change |
| 1 | 25 | Language chosen on step 1 is the language messages go in | `DEF-CUS-9195` |
| 2 | 12 | Pricing table gets a Charge code column | change |
| 2 | 13, 14 | Account type shows the plan's customer class; Budget billing off step 2 | `DEF-CUS-9200` |
| 2 | Q7 | City/State mismatch says why; Unit, apt. hidden for an apartment complex | change |
| 3 | 15 | Unit type in Common selection and per row | change |
| 3 | 16, 17 | Whole-build work-order rows and *+ Add work order* get one Applies-to and a work-order dropdown, editable | change |
| 3 | 18 | *Press Apply to all first* only while rows are empty | `DEF-CUS-9199` |
| 4 | 19 | Payment terms: 7 / 15 / 30 / 60 / 90 days | change |
| 4 | 20 | What is charged above Who is billed and Payment | change |
| 5 | 21, 29, 30 | At a glance: real work-order count; meters and behind-the-meter devices apart | `DEF-CUS-9197` |
| 5 | 22, 23, 46, 24, 31 | Messages: one editable table, template per row or *No template — add in Settings*, When = On approval, counted as Sent on approval | `DEF-CUS-9198` |
| 5 | 26 | The charges line shown once | change |
| 5 | 47 | What Create makes shows each item's lifecycle status | change |
| all | 27, 28 | Premises made on Create, Pending; *Master account*, never *the owner's account* | `DEF-CUS-9196`, `DEF-CUS-9197` |

## 2 · Status

**Wave 1 BUILT at `2.463.0`** — every item in the table above, plus `DEF-CUS-9212` (a
single-family build with a charge reached Create and failed). Judgments where the rulings
stopped are the decision-log row of 2026-10-02 headed *"`CR-164-BRC10` (lane NC-C,
2.463.0) — EIGHT JUDGMENTS"*. Still OPEN: the owner's own custom fields on step 1
(`NEW_CONNECTION_OWNER` slot, handed over by the custom-fields lane) — wave 2.

### What the server now does that it did not
- `POST /customers/match` (new, read-only, AdminOrClerk) — Q5's lookup, `apps/customers/owner_lookup.py`.
- `create_master_account` and `connections.create_owner_account` accept the owner's
  `preferred_language`, `paperless` and `sms_reminders` (step 1's Communication panel,
  dropped until now — `DEF-CUS-7863`).
- `rating.selectors.plan_detail` serves each service line's `base_charge_code` (a read;
  it prices nothing). ⚠ `rating/selectors.py` and `metering/connections.py` are on the 🔒
  human-owned list: the two additions are a read-only field and three keys on an allow
  list, and they are named here so the reviewer sees them.

### Proof
- Chromium walk `10-scripts/ncc_new_connect_wizard_walk.mjs`, pressing Create, on a private
  PostgreSQL 16 clone: single-family (`CON-26-0129`, no charge), apartment complex
  (`CON-26-0130`, $225.00 charge, $25.00 card), commercial building (`CON-26-0131`), and a
  repeat owner whose Tax ID shows **Match** with *Use this customer*.
- Tests: `tests/test_cr164_owner_lookup.py`, `tests/test_cr164_owner_preferences.py`
  (PostgreSQL-free, proved red first), `newConnectCr164.test.ts` and the step test files.

### Collision put to the coordinator (law 13)
Q8 *"language from step 1"* against `OQ-CUS-12619` (*"Portal only; emails in English"*).
The language now reaches the account; the SEND language is unchanged until ruled.

### Wave 2 — BUILT at `2.464.0`: the owner's own customer fields
Handed over by the custom-fields lane (`CR-161-BRC10` W4, 2.461.0), which declared the slot
`NEW_CONNECTION_OWNER` and switched it off because the answers had no road to the customer.
The road: Step 1 `ownerCustomData` → the commit's owner block `customer_custom_data` (sent
always for a new owner, never over a picked customer) → `_owner_block_in_the_doors_language`
puts it on the customer block → `create_master_account(..., customer_fields_screen=
"NEW_CONNECTION_OWNER")` validates it AS THAT SLOT → the new customer row. The slot is
switched on in `SLOTS` in the same commit. Proved: `tests/test_cr164_owner_custom_fields.py`
(red with the connections line removed), the W1 pairing test green, and the Chromium walk —
`CON-26-0132`'s owner customer `C-00055` holds `{"loyalty_tier": "Gold"}`, its master
account `preferred_language = es-MX`, its three units `residential_submetered`.
⚠ `customers/services.py` gained one keyword (`customer_fields_screen`, default `None`, so
every other caller is unchanged) and 🔒 `metering/connections.py` passes it.

### Rollback
Wave 1: redeploy 2.462.2. Wave 2: redeploy 2.463.0. No migration in either.

### Wave 3 — BUILT at `2.467.0` (lane NC-R): the PO's rulings 1 and 2 of 2026-10-02

Decision log, *"SEVEN PO ANSWERS IN ONE MESSAGE"*, verbatim:
1. *"A. The owner asked for the work, so the owner pays. With B, the bill could land on a tenant
   who moves in later, or never go out at all."* — **supersedes this CR's `DEF-CUS-9212` step-4
   refusal** (*"No master account to bill. Remove the charges."*). Built under `DEF-CUS-9228`.
2. *"A with the English fallback. She asked for Spanish. Today her choice is saved but never
   used."* — **settles the collision recorded above** (Q8 against `OQ-CUS-12619`) for New
   Connection letters only. Built under `DEF-CUS-9195`.

What was built:
- `customers.create_build_owner_account` — the owner's REGULAR account on the build's one home,
  through `_open_account`; created Active for the Create act's invoice and payment, then held
  Pending by the commit, Active on approval (`activate_pending_master_account` now takes it,
  through `_make_occupying`). An occupant who moved in before approval keeps the home and the
  owner's account stays Pending, reported (`left_pending`), never refused.
- `metering.create_owner_account` picks it when the premises TYPE says Regular and the address
  holds exactly one home (`_single_family_home`); every other case is the master door, unchanged.
- Step 4 offers *Owner's account · <owner>*; step 5 reads *Owner's account 1* / *Customer record
  and ID 1*; the refusal remains only where Create opens no owner's account at all.
- `_letter_language`: the owner's stated language where the utility published that letter in
  it (exact, then base language), the utility's otherwise; the Messages tab shows each copy's
  language.

Proof: `tests/test_def_cus_9228_single_family_owner_pays.py` (PostgreSQL 16: Maria, CONN 2 ×
$45 + INSPECT $30 = **$120.00** on her own regular account, $120.00 card settled against that
bill; red first: 4 of 5 failed `master_not_for_single_family`), `tests/test_def_cus_9195_new_connection_letter_language.py`
(red first 3 of 5), `NewConnectOwnerPays.dom.test.tsx` (red first 5 of 6). Chromium walk
`10-scripts/ncr_single_family_charges_walk.mjs` on a private clone: `CON-26-0130` single-family,
$45 + $30 = $75.00 on `AC-2026-00055` (regular, Pending), card $75.00 on the same account
(`10-scripts/ncr_owner_pays_readback.sql`); `CON-26-0131` apartment, owner Español, *Build
confirmed* pinned `es` (before: `default` on `CON-26-0129`).

Known, not this wave's: Add fee before approval refuses on every build (`DEF-MET-9217`), held
here by a strict xfail. Rollback: redeploy 2.466.6; no migration.

### Wave 4 — the PO's ruling of 2026-10-03, item 1: the owner holds the home only if they live there

⚠ **REOPENED THE SAME DAY — `OQ-CUS-12785` (OPEN).** After *"C"* below the PO answered *"B"*
(never: the owner's account only pays the connection charges, the home stays vacant), and asked
once more which stands: *"i dont know yet"*. **So only what B and C share is built (2.468.0):**
every owner type except an owner-occupier opens the owner's account billing only. **An
owner-occupier keeps TODAY's behaviour** (the account holds the home, as 2.467.0) until
`OQ-CUS-12785` is answered — chosen over a `NotImplementedError` because a raise would refuse every
owner-occupier's New Connection at Create, while holding the home is what already happens and a
Move-out undoes. Under B the one change is `OWNER_TYPES_THAT_LIVE_THERE = frozenset()` and its
screen mirror `ownerLivesThere`; under C nothing changes. Read the judgments below with that in
mind: (1) is the shared half; the *"ONLY `owner_occupier` holds"* clause is the open half.

Requester's words (decision log 2026-10-03, *"TWO PO ANSWERS"*, item 1), verbatim: *"C By owner
type: an owner who lives there holds it; a landlord or builder doesn't"*. Shown: *Maria owns 14
Oak St; approval makes her own account Active and today it also holds the home as occupant —
right if she lives there; if she is a landlord, her tenant Jose cannot move in until her account
is moved out.*

Classified: **a change** to wave 3's judgment (b) (*"Active means the owner's account holds the
home"*), which the PO has now overruled for non-occupying owners. Money: none moves — the build's
charges are still billed to the owner's account at Create (ruled 2026-10-02, unchanged).

Judgments where the ruling stops (law 13 — recorded, not put back):
1. **Who "lives there".** Step 1's *Owner type* is the tenant's `owner_categories` list
   (`BR-TEN-150`: `owner_occupier` · `landlord` · `property_manager` · `hoa` · `builder`). Only
   **`owner_occupier`** (and the pre-`DEF-CUS-9192` stored code `occupier`) means the owner lives
   there. Every other code — the four seeded non-occupiers, the legacy `builder_developer` /
   `property_owner` / `landlord`, a code the utility added itself, and no answer at all — is
   **billing only**. Reason: a home wrongly held blocks a tenant's Move-in until somebody moves the
   owner out; a home wrongly left vacant costs one ordinary Move-in. The cheaper mistake is the
   default.
2. **What "billing only" is in the data.** A regular account that names the premises and **no
   unit** (`accounts.billing_only = true`), so nothing reads it as the home's occupant — occupancy
   and every bill-run scope key off the unit. `ck_accounts_regular_has_unit` is relaxed for exactly
   that flag and a new `ck_accounts_billing_only_has_no_unit` makes the flag unable to occupy.
   Opened Active for the Create act's charges, held Pending, Active on approval — the same
   lifecycle — and **no service agreement is ever written for it**, so no cycle run bills it base
   or usage for the home.
3. **Screens.** Step 5's *What Create makes* reads *Owner's account · lives there* or *Owner's
   account · billing only*; the build's record (*Owner and scope*) says which the account is.

Worked: Maria, Owner type *Landlord*, 14 Oak St → Create bills $120.00 to her account; approval
makes it Active, billing only; Unit 1 stays Vacant and Jose's Move-in opens his own account with
nobody moved out. Maria, *Owner-occupier* → exactly as 2.467.0.
