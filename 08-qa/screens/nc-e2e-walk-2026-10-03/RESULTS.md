# New Connection — end-to-end web walk, 2026-10-02 / 03

**What was walked:** eight buildings through New Connection in a real Chromium against a
real PostgreSQL 16. Every building went through all fourteen stages: the five wizard
steps, Create, the request page and its actions, crew results and acceptance, partial
then full approval, a database read-back, the master account's first bill, and the two
refusals (another utility, and a role that may only look).

**Where:** walk database `ncw_e2e`, utility *Lakeside Junction Utilities* (`lakeside`, all
eleven services, America/Chicago). The second utility *Brazos Bend* was used for the
refusals. The builds are `CON-26-0129` to `CON-26-0150`.

**Builds tested:** from 2.465.0 to 2.467.14. The closing re-walk ran on 2.467.14.

**Scripts:**
- `10-scripts/nc_e2e_walk.mjs` covers stages 1–7.
- `10-scripts/nc_e2e_walk_after.mjs` covers stages 8–11.
- `10-scripts/nc_e2e_walk_readback.py` is stage 12.
- `10-scripts/nc_e2e_walk_negatives.mjs` is stage 14.

**Screenshots:** 470 screenshots named `nce2e_<S#>_<stage>.png`. Each was checked to be over
20 KB, and a sample was opened by eye. A selection is kept in this folder.

## 1 · The eight buildings

| # | Building | Owner (kind · category) | Account type · sub-type | Services | Units |
|---|---|---|---|---|---|
| S1 | Apartment complex | Harbor Point Builders LLC (company · builder) | residential · permanent, **es-MX** letters | electric, water, gas, sewer, trash, storm water, broadband | 3 + common area |
| S2 | Commercial building | Delgado Retail Holdings Inc (company · landlord) | commercial · permanent | electric, water, **fire 6" + 2×2"**, solar, battery, thermal | 2 |
| S3 | Mixed-use | Tomas Reyes (person · owner-occupier) | industrial · permanent | electric, water, sewer, trash | 2 |
| S4 | Single-family | Maya Whitlock (person · owner-occupier) + co-applicant | residential · permanent | water, sewer, trash | 1 |
| S5 | Agricultural | Ellen Haverford (person · owner-occupier) | agricultural · construction/temporary | electric, water | 1 |
| S6 | Institutional | St. Brendan Academy Trust (company · property manager) + co-applicant | institutional · permanent, fr-CA | electric, water, gas, sewer | 2 + common area |
| S7 | Municipal | City of Lakeside Public Works (company · HOA) | municipal · permanent | electric, water, storm water | 2 |
| S8 | Repeat owner of S1 | Harbor Point Builders LLC (matched by Tax ID) | builder/developer · permanent | electric, water | 2 |

## 2 · Pass / fail, building × stage (latest run of each)

| Building | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 14a | 14b |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NEG |  |  |  |  |  |  |  |  |  |  |  | 8 ✓ | 10 ✓ |
| S1 | 6 ✓ / 1 ✗ | 4 ✓ | 1 ✓ | 1 ✓ | 3 ✓ | 4 ✓ | 8 ✓ | 12 ✓ | 4 ✓ | 3 ✓ | 2 ✓ |  |  |
| S2 | 5 ✓ / 1 ✗ | 4 ✓ | 1 ✓ | 1 ✓ | 3 ✓ | 4 ✓ |  |  | 4 ✓ | 3 ✓ | 2 ✓ |  |  |
| S3 | 9 ✓ / 3 ✗ | 8 ✓ | 2 ✓ | 2 ✓ | 6 ✓ | 4 ✓ |  |  | 4 ✓ | 3 ✓ | 2 ✓ |  |  |
| S4 | 14 ✓ / 2 ✗ | 8 ✓ | 2 ✓ | 2 ✓ | 6 ✓ | 4 ✓ | 8 ✓ | 10 ✓ | 4 ✓ | 3 ✓ | 2 ✓ |  |  |
| S5 | 12 ✓ / 2 ✗ | 8 ✓ | 2 ✓ | 2 ✓ | 6 ✓ | 4 ✓ | 8 ✓ | 9 ✓ | 6 ✓ | 3 ✓ | 2 ✓ |  |  |
| S6 | 6 ✓ / 1 ✗ | 4 ✓ | 1 ✓ | 1 ✓ | 3 ✓ | 4 ✓ | 8 ✓ | 9 ✓ | 6 ✓ | 3 ✓ | 2 ✓ |  |  |
| S7 | 5 ✓ / 1 ✗ | 4 ✓ | 1 ✓ | 1 ✓ | 3 ✓ | 4 ✓ | 8 ✓ | 11 ✓ | 6 ✓ | 3 ✓ | 2 ✓ |  |  |
| S8 | 7 ✓ | 4 ✓ | 1 ✓ | 1 ✓ | 3 ✓ | 4 ✓ | 8 ✓ |  | 4 ✓ | 3 ✓ | 2 ✓ |  |  |

Each cell is checks passed ✓ and failed ✗. Stages 1–7 come from the part-1 run and stages 8–11 from part 2; the latest run of each part is counted, so S2, S3 and S8's stage 7–8 checks sit in earlier runs and are not repeated here.

Every red cell above is accounted for. None is an open product defect:

- **"A new owner is not found" on S1–S5 step 1.** On a re-walk the owner already exists, so
  the lookup correctly finds them. The check is right the first time and expected to fail on
  a re-run.
- **S5 "name + date of birth is a possible match".** The earlier owner it looks for, Maya
  Whitlock, was saved before `DEF-CUS-9256` was fixed, so her birth date was never stored.
  After the fix, Ellen Haverford is stored with her birth date and is offered as a possible
  match (§7).
- **The S5–S7 stage 8–9 reds from the first run.** These are superseded by the closing
  re-walk (§9).

## 3 · Accounts made, by building

The owner's account is the only account New Connection opens. Units are left vacant with the
service off, so no tenant account is opened (`BR-MET-116`). Times are UTC; the utility's
clock is 5 hours earlier.

| Build | Property type | Owner's account | Kind | At Create | After approval |
|---|---|---|---|---|---|
| CON-26-0129 (S1) | apartment complex | AC-2026-00054 | master | Pending | Active (partly activated) |
| CON-26-0131 (S2) | commercial | AC-2026-00056 | master | Pending | Active |
| CON-26-0133 (S3) | mixed-use | AC-2026-00057 | master | Pending | Active |
| CON-26-0132 (S4, before the PO's ruling) | single-family | none | — | — | — |
| **CON-26-0144 (S4, after the ruling)** | single-family | **AC-2026-00067** | **regular** | Pending | Active |
| CON-26-0134 (S5, before) | single-family | none | — | — | — |
| **CON-26-0148 (S5, after)** | single-family | **AC-2026-00071** | **regular** | Pending | Active |
| CON-26-0135 (S6) | commercial | AC-2026-00058 | master | Pending | Active |
| CON-26-0136 (S7) | government | AC-2026-00059 | master | Pending | Active |
| CON-26-0137 (S8) | apartment complex | AC-2026-00060 | master | Pending | Active |
| CON-26-0140 (S2, re-walk) | commercial | AC-2026-00063 | master | Pending | Active |
| CON-26-0141 (S1, re-walk) | apartment complex | AC-2026-00064 | master | Pending | Active |
| CON-26-0142 (S8, re-walk) | apartment complex | AC-2026-00065 | master | Pending | Active |
| CON-26-0143 (S3, re-walk) | mixed-use | AC-2026-00066 | master | Pending | Active |
| CON-26-0146 (S1, final) | apartment complex | AC-2026-00069 | master | Pending | Active |
| CON-26-0149 (S6, final) | commercial | AC-2026-00072 | master | Pending | Active |
| CON-26-0150 (S7, final) | government | AC-2026-00073 | master | Pending | Active |
| CON-26-0147 (stage 14 target) | apartment complex | AC-2026-00070 | master | Pending | left Pending on purpose |

## 4 · What each item is before and after approval

| Item | At Create | After approval |
|---|---|---|
| Property | Pending | Active |
| Owner's account (master or single-family regular) | Pending activation | Active |
| Units | Pending | Active on their first activated service |
| Service points | Pending | Activated, service by service, when approved |
| Meters and devices | Inventory | Installed, with an install date |
| Work orders | Raised per build | Completed by the crew result, then accepted |
| Quote (a fee bill) | Raised and issued at Create | Unchanged |
| Letters | "Sent on approval" | Queued when the build is approved |

Partial approval activates what is ready; a gate that has not passed holds its own service
back (for example "Trash: gate WO-0215 not passed"). Sewer and storm water carry no gate, so
they can be activated with no work order completed.

## 5 · Payments

| Account | Payment | Tender | Amount | Reference | Status | Met the bill? |
|---|---|---|---|---|---|---|
| AC-2026-00055 (S2) | PY-261002-0087 | card at Create | $90.00 exact | AUTH-S2-… | cleared 10/02 | yes, balanced entry DR 1010 / CR 1200 |
| AC-2026-00054 (S1) | PY-261002-0086 | card at Create | $50.00 part | AUTH-S1-… | processing (no clearing date) | not yet — by design |
| AC-2026-00054 (S1) | PY-261002-0090 | **cheque 4471** | $40.00 part | 4471 | processing | not yet — by design |
| AC-2026-00057 (S3) | PY-261002-0091 | **cash** | $90.00 exact | — | processing | not yet — by design |
| AC-2026-00059 (S7) | PY-261002-0092 | **ACH** | $90.00 exact | ACH-900114 | processing | not yet — by design |
| AC-2026-00060 (S8) | PY-261002-0093 / 0094 | card | $30.00 part (twice, re-walk) | AUTH-S8-0030 | processing | not yet — by design |

A payment with no clearing date stays *processing*. It meets no bill and posts no ledger
entry until it clears (`BR-PAY-021`). The payments taken at Create with a clearing date were
applied straight away, each with a balanced entry (for example `JE-100226-0213`, $90.00).
After `DEF-MET-9224` a cheque taken on the request page is listed under *Paid so far*. Every
payment queued a receipt by email and on paper. A text copy is queued only where the owner
has a mobile number, and the Created screen now names that channel (`DEF-MET-9245`).

## 6 · Messages

| Letter | Channel | Language | State |
|---|---|---|---|
| Build confirmed (`new_connect_confirmed`) | email | default, or **es-MX** where published | queued — 24 copies, 1 in Spanish |
| Quote and what is owed (`new_connect_quote`) | email · print | default | queued — 19 copies |
| The contract (`contract_service_agreement`) | print | — | queued (6) where a template exists; otherwise "Not sent — No template" |
| Schedule of works / inspection booked | — | — | "No template — add one in Settings → Templates" (not queued, `DEF-MET-9229`) |
| Payment receipt | email · print · text | default | queued; text needs a mobile number |

Nothing is ever *sent*: email and text dispatch are switched off and print has no provider
(`BR-NOT-013`). Each letter now carries the customer's name, the account number and the
service address (`DEF-MET-9232`).

**Letter language** (PO ruling of 2026-10-02):

- S1's owner chose Español (México). Before the utility published a Spanish version, the
  letter went in the utility's default wording. After a Spanish (es-MX) "Build confirmed"
  was published, the next copy was pinned to `es-MX`.
- The Messages tab shows each copy's language.

## 7 · Matching an existing customer (step 1)

| Typed | Earlier owner | Answer |
|---|---|---|
| Tax ID 74-3318620 | Harbor Point Builders LLC | MATCH C-00052 ✓ |
| SSN 523-41-7788, another name | Maya Whitlock | MATCH C-00057 ✓ |
| Driver's licence TX-40017788, another name | Maya Whitlock | MATCH C-00057 ✓ |
| Name + date of birth | Ellen Haverford (saved after the `DEF-CUS-9256` fix) | POSSIBLE C-00058 ✓ |
| Name + date of birth | Maya Whitlock (saved before the fix) | not found — her birth date was never stored |

## 8 · The first bill for a master account (stage 13)

**The one that worked** — S3-type industrial master `AC-2026-00066`, November draft
`BL-2611-000121`, run "NC walk Nov no fire". It bills two empty units by the day to the
master:

| Line | Per unit | × 2 units |
|---|---|---|
| Electric base BASE-E-IND | $180.00 | $360.00 |
| Water base BASE-W-COM | $26.25 | $52.50 |
| Trash base BASE-T | $0.00 | $0.00 |
| **Subtotal** | | **$412.50** |
| Local tax 2% | | $8.25 |
| TX state tax 6.25% | | $25.78 |
| **Total** | | **$446.53** — the lines add up to the total |

**The ones that did not** are all billing (money) questions, filed and handed back:

- `DEF-BIL-9251` — a fire master is refused "connection size not recorded", although every
  fire line is sized (6" + 2×2" on unit 1, 6" on unit 2). The expected fire charge on
  unit 1 is $60 + 2 × $12 = $84.00.
- `DEF-BIL-9252` — a common area with no plan, which the PO allowed on 2026-09-16, blocks
  the master's bill with "unit has no plan".
- `DEF-BIL-9253` — a builder/developer master's base charge prices at $0.00 and nothing
  flags it (`BL-2611-000120`).
- `DEF-BIL-9254` — the quote raised at Create counts as "billed through 2026-10-03". The
  November run asks a false continuity question, and an October run would start on 10/04,
  charging $180.00 × 28/31 = $162.58 instead of a full first bill.
- `DEF-BIL-9255` — a draft run cannot be discarded (DELETE answers 405), so it blocks every
  overlapping run.

## 9 · Stage 14 — the two refusals (`nc_e2e_walk_negatives.mjs`, 20/20 on 2.467.7+)

| Who | What | Answer |
|---|---|---|
| Avery Cole, Executive (view only) | opens the request | can read it ✓ |
| Executive | Approve, Raise order, More, Take payment, Add fee, Send now, Activate | each greyed out with "Your role can view this but not change it." (`DEF-MET-9238`) ✓ |
| Executive, through the API | activate · hold · fees · units · messages send · commit | 403 every time ✓ |
| Dana, Brazos Bend System Admin | the Lakeside request id under her own utility (screen and API) | not found ✓ |
| Dana | the Lakeside address in the browser | sent to Lakeside's sign-in page (`DEF-SHL-9241`) ✓ |
| Dana | the Lakeside API, read and write | 404 every time; her own list holds none of the walk's builds ✓ |

## 10 · Defects found by this walk

| Defect | What a user saw | Fixed in |
|---|---|---|
| DEF-MET-9213 | A payment taken in the evening was dated tomorrow | 2.465.1 |
| DEF-MET-9216 | The "what is owed" letter was never queued | 2.466.1 |
| DEF-CUS-9218 | Units tab hid the 6" fire line ("FL-2 · 3") | 2.466.1 |
| DEF-CUS-9219 | Add unit: free-text type, cramped boxes, no error on "no service" | 2.466.1 |
| DEF-CUS-9220 | Size lists out of order (12" before 2") | 2.466.1 |
| DEF-MET-9221 | Meters lost the step-3 size at Create | 2.466.2 |
| DEF-MET-9224 | A cheque taken on the request was not listed under Paid so far | 2.466.2 |
| DEF-MET-9229 | A letter with no template read "Queued" | 2.466.3 |
| DEF-MET-9230 | A new connection's units were on no route and no billing cycle | 2.466.5 / 2.466.6 |
| DEF-MET-9217 | Add fee refused "cannot be priced" before approval | 2.467.1 (🔒 review row) |
| DEF-MET-9232 | Letters had no name, account number or address | 2.467.2 |
| DEF-MET-9236 | An evening build's quote dated tomorrow, and a next-day fee was refused | 2.467.4 |
| DEF-MET-9238 | Executive saw live buttons that all failed | 2.467.6 |
| DEF-SHL-9241 | Another utility's address showed a dead Retry page | 2.467.7 |
| DEF-MET-9244 | Units tab showed raw unit-type codes | 2.467.9 |
| DEF-MET-9245 | "A receipt has no recipient" when only the text copy lacked a number | 2.467.9 |
| DEF-CUS-9242 | (custom-fields lane's find) a blank required property field passed step 2 | 2.467.10 |
| DEF-MET-9250 | Properties added to a route automatically were in no billing cycle | 2.467.12 (🔒 migration 0069) |
| DEF-CUS-9256 | The owner's date of birth was never saved | 2.467.14 |

**Handed back, not fixed** (money paths or a design question): `DEF-MET-9222` (thermal
tonnage and storm-water class dropped; step 5 counts a thermal meter never fitted),
`DEF-MET-9223` (work orders are raised per build, never per unit), and `DEF-BIL-9251` to
`DEF-BIL-9255` (§8).

**Red before this lane started** — each checked with `git log -S`:

| Defect | What is red | Since |
|---|---|---|
| DEF-MET-9207 | `test_br_met_1187` and the `test_cr109_*` PostgreSQL tests stop at "a master needs two homes" | e72e3347c, 2026-10-02 |
| DEF-MET-9206 | `test_new_connect_step7_messages … will_not_go_without_it` | unchanged since 1412ce149 |
| DEF-MET-9249 | three route tests | stale since CR-131, a598bd4ef, 2026-09-22 |

## 12 · Re-walk after the four New Connection fixes (2.467.25, 2026-10-03)

A fresh walk database `ncl_walk` (utility signed up through `POST /api/tenants`, all eleven services), stages 1–7 of
S2, S1 and S7 with `nc_e2e_walk.mjs`, then a database read-back.

| Build | Review said | Create made | Sizes recorded on the units | Work orders |
|---|---|---|---|---|
| S2 `CON-26-0130` | Meters 4 · Work orders 25 | 4 meters · 25 orders | thermal 10 ton on each of 2 units | 18 on a unit, 7 per-premise on the whole build |
| S1 `CON-26-0131` | Meters 12 · Work orders 31 | 12 · 31 | storm water 6 ERU on each of 4 units (*Apartment building*, the first class on the list) | 24 on a unit, 7 whole build |
| S7 `CON-26-0132` | Meters 4 · Work orders 8 | 4 · 8 | storm water 6 ERU on each of 2 units | 6 on a unit, 2 whole build |

Before the fixes: S2's review said 6 meters and Create made 4; no thermal or storm-water size was recorded; every order
stood on the whole build. A company owner's step 1 now shows no Date of birth (S7), and *Add unit* on S7 offers
Electric, Water and Storm water — the build's three — not eleven. Check failures on the re-walk: S2 1 (the owner
already exists on a re-walk, expected), S1 1 (the walk database has no utility customer field defined), S7 0.

Found by the re-walk and filed: `DEF-WRK-9266` — thermal still proposes a *Meter set* and solar a *Net meter swap*.
Screenshots: `ncl_S2_step5_meters4_orders25.png`, `ncl_S2_work_tab_per_unit.png`, `ncl_S7_step1_company_no_dob.png`,
`ncl_S7_add_unit_build_services.png`.
