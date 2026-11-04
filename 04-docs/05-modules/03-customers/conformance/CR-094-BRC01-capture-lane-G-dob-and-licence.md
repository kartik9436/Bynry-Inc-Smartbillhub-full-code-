# `CR-094-BRC01` lane G — the date of birth and the driving licence land on a service request

**2026-09-15 · 🔒 sensitive path (personally identifying information, app-layer
encryption) · `HUMAN-REVIEW-PENDING` · migration `customers 0050`**

## What this finished, and why it is not an override

PO, verbatim, having been shown the blueprint's step 1 beside the product's:

> *"ensure user is able to inputs both these on step 1 - Date of birth and
> driver's licence on step 1 ... rewrite this rules if required"*

⚠ **The permission to rewrite is recorded and was DECLINED as unnecessary, for
the SECOND time on this rule.** The PO offered the same on 2026-08-24 and
`BR-CUS-092` already records why it was declined then: accepting it would
misrepresent the position. **Clause (a) of that signed rule has read *"both
identifiers are captured on the service request"* since 2026-08-24**, and the
amendment of 2026-08-31 says in capitals what was outstanding. This is that half
landing. **No supersession note was written, because there is no superseded
statement to name.**

**What it unblocks is worth more than two columns.** `BR-CUS-089` (PO
2026-08-25, closing `OQ-364`) makes a STRONG identity match **name + date of
birth + one government ID**, and `BR-CUS-1020` records the cost of the gap
verbatim: *"until the request form captures a DOB, no match can be assessed
against them."* Signed criteria that **no service request could ever satisfy**,
for three weeks, with nothing red — because an absence is invisible to every
check this repo has.

## The pages read as images

`p075.png` and `p076.png` from `05-prototype/02 Accounts Menu Blueprint.pdf`,
rendered at **scale 2** into
`/tmp/…/scratchpad/acct/`, read with the Read tool as IMAGES (B14 rule 42).
`p076`'s lower half draws step 1: `Channel *` · `Full name *` · `Email` ·
`Phone` · **`Date of birth`**, placeholder *"if known"*, with a date-picker
glyph · **`Driver's licence`**, showing `TX ••••882` · `SSN`, showing
`•••-••-4417` · `Add a co-applicant`. The right rail carries two sentences:
*"Optional on a staff-raised request."* and *"Stored encrypted at the
application layer, shown as the last four."*

⚠ **`TX ••••882` and `•••-••-4417` are ILLUSTRATIONS (B14 rule 37)** — the SHAPE
is *a state prefix, a mask, four characters*, and nothing here builds to those
digits. ⚠ **The drawn label is `Driver's licence`; our catalogue's
`applicant.driversLicence` reads `Driving licence`.** That is the CAPTURE
screen's label and that screen is the capture-wizard lane's; it is named here
rather than changed, because the detail screen's own blueprint (B19 §7) was not
read by this lane.

⚠ **No kind selector is drawn on step 1 in that frame** — it opens at `Channel`.
The kind control is the capture lane's; the server-side refusal it implies is in
this lane and is built (below).

## Before → after

| | Before 2026-09-15 | After |
|---|---|---|
| `service_requests.date_of_birth` | no column; `_clean_capture` refused the name with `BIZ_STATE` | a plain, comparable `DateField` in `CAPTURE_FIELDS` |
| `service_requests.drivers_licence` | no column, and **no named refusal either** — see the correction below | `EncryptedTextField`, `crypto_context="service_requests.drivers_licence"` |
| the blind index | none | `drivers_licence_bidx`, `bix1:<kid>:<HMAC-SHA256>`, btree `ix_sr_drivers_licence_bidx` |
| the detail payload | `drivers_licence_absence: {tracks: "BR-CUS-092"}` and `date_of_birth_absence: {tracks: "DEF-638"}` | `identifier.drivers_licence_last4` and `date_of_birth`, both real values |
| `SERVICE_REQUEST_UNAVAILABLE` | declared `applicant_drivers_licence_not_captured` | that entry is retired |
| `identity_match.evidence_from_service_request` | `date_of_birth=None,  # DEF-638(2) — REQ-03.1 collects none` | lifts the date of birth AND the licence |
| `AUDIT_MASKED_FIELDS` | `{"ssn"}` | `{"ssn", "drivers_licence"}`, asserted against the MODEL |
| `capture_applicant_identifier` | a stub raising `NotImplementedError("BR-CUS-092(a)")` | deleted; its subject is built |

## ⚠ The rule was wrong about the code, and it had already been quoted onward

`DEF-CUS-5410`. `BR-CUS-092`'s amendment of 2026-08-31 says in capitals that
*"`_clean_capture` refuses it by name"*. **It never did.** Measured at the tip
before anything was built: no spelling of the licence was in
`IDENTIFIER_FIELDS`, so `drivers_licence`, `driving_licence` and
`drivers_license` all fell to the *unknown field* branch and answered
`VAL_UNKNOWN_LOOKUP` — *"This form does not accept …"* — rather than `BIZ_STATE`'s
*"We cannot store an identity number yet"*.

**One refusal says WE HOLD THIS FACT AND MAY NOT STORE IT; the other says WE
HAVE NEVER HEARD OF THIS FIELD**, which is the entire reason that list exists.
The sentence was plausible because twelve of its neighbours WERE refused by
name, and it had already been quoted verbatim into the decision-log row of
2026-09-15 and into this wave's brief. **The wrong text is left visible under a
dated stamp rather than deleted**, because a reader who followed it needs to
find out that it moved.

## The payload, published so a screen builds from the repo

`GET /service-requests/{id}` → `applicant`:

```jsonc
{
  "identifier": {
    "ssn_last4": "4471",
    "ssn_present": true,
    "stored_encrypted": true,                    // ⚠ this one is the SSN's
    "drivers_licence_last4": "4882",
    "drivers_licence_present": true,
    "drivers_licence_stored_encrypted": true
  },
  "date_of_birth": "1988-03-14",                 // in FULL, not under identifier
  "acting_for_absence": { "tracks": "DEF-638" }  // still true, still stated
}
```

**Writing them** — `POST /service-requests` and `PATCH /service-requests/{id}`
take `date_of_birth` (`YYYY-MM-DD` or a `date`) and `drivers_licence` (stored
exactly as typed). A worked case end to end: an applicant gives `TX-1234882` and
`1988-03-14`; the raw column holds `sbh1:<kid>:<nonce>:<ciphertext>` and no
spelling of `1234882`; every read path shows `4882`; `audit_log` carries
`•••••4882`; and `tx1234882` typed on Thursday finds the same row, because the
index normalises punctuation and case while the ciphertext keeps what was typed.

**Refusals, each BY NAME:** `driversLicenceTooShort` (fewer than four
alphanumerics — derived from the last-four projection, not a chosen format
rule) · `dateOfBirthInvalid` · `useCanonicalFieldName` for `dob`, `driving_licence`,
`drivers_license`, `driving_license`, `dl` and `date_of_birth_iso`, each carrying
the canonical name · `notAskedOfThisApplicant` for a business asking for either.

## Four judgments this lane made

1. **The column is `drivers_licence`; the customer's stays `driving_licence`.**
   Two spellings of one fact is a hazard and renaming either moves every
   citation at once, so neither is renamed and BOTH are answered.
2. **`dob` moved from *refused identifier* to *refused alias*.** Its old
   sentence stopped being true the moment the column landed, and a refusal that
   has expired is worse than no refusal.
3. **`stored_encrypted` keeps its name and its meaning (the SSN's).** Renaming
   it would edit a 🔒 signed proof's assertions for a cosmetic gain. **Rename it
   when a THIRD encrypted identifier arrives, not before.**
4. **`ssn` was NOT narrowed to persons in passing** → `DEF-CUS-5409`.

## Proof

| What | How | Result |
|---|---|---|
| `tests/test_br_cus_092_licence_and_dob_capture.py` | 22 cases, `JOBS_EAGER=false pytest --reuse-db` | **49 passed** with the SSN suite beside it |
| the raw column holds no readable characters | a SECOND cursor, never `.values()` | `sbh1:insecure-dev:…`, and every spelling of `1234882` absent |
| AAD binds to THIS column | decrypt under `customers.driving_licence`, `service_requests.ssn`, `tenants.ein` | all three RAISE |
| randomised, not deterministic | the same licence captured twice | two different ciphertexts |
| the blind index | written, matched, moved and cleared with the value | `bix1:<kid>:<HMAC>`, `tx1234882` finds the row |
| the audit trail | asserted at the SINK, not by querying afterwards | `•••••4882`, and no `bix1:` token either |
| every encrypted column is masked | the set read against the MODEL | no `EncryptedTextField` is missing from `AUDIT_MASKED_FIELDS` |
| a wrong key fails closed | `override_settings` with a second key, then with none | `FieldDecryptionError`, then `FieldEncryptionUnavailable` |
| the seam reads all three facts | `evidence_from_service_request` | name, DOB, SSN and licence all present |
| RLS, hard rule 1 | `pg_class.relforcerowsecurity` + `pg_policies` on PostgreSQL | `FORCE` still on, three columns present, **ONE** policy |
| `tsc` | proved able to FAIL first | `TS2739: … is missing drivers_licence_last4, drivers_licence_present, drivers_licence_stored_encrypted`, then exit 0 |
| `vitest` | detail page, dom test, capture test, Tailwind ledger | **106 passed** |
| `ruff` / `black` | mine clean; the four shared files match the tip's baseline complaint-for-complaint | no new formatting debt added |
| `makemigrations --check` | single leaf | *No changes detected in app 'customers'* |

**Red proofs, quoted:**

* `assert '•••••4882' == '••••••4882'` — the mask literal, on the first run.
* `MISSING in service_request_service.py: 'elif key == "drivers_licence"'` — the
  marker check, proved red by deleting the branch it guards, then green again.
* `TS2739: Type '{ ssn_last4: null; … }' is missing the following properties …`
* `CommandError: Conflicting migrations detected; multiple leaf nodes in the
  migration graph` — **twice**, when sibling lanes took `0047` and then `0049`.

## Two things that went wrong in this lane, and what they cost

**1 · A re-derivation silently dropped a hunk, twice.** Re-applying my own edits
onto a moved tip with `git apply --reject` lost
`CAPTURE_FIELDS`' two new names among hundreds of *"applied cleanly"* lines.
**Everything downstream still passed**: the module imported, `ruff` and `black`
were clean, `makemigrations --check` said *no changes*, `tsc` was green. Only
reading the CONSTANT caught it. **A diff tells you what moved; only a marker
tells you what is THERE** — so this lane's push now runs a marker check
(30 markers present, 5 retirements confirmed) before it will push, and that
check was itself proved red on the exact hunk that was lost.

**2 · The locale catalogues came back MISSING THREE KEYS a sibling had added**,
because a failed run exited before its locale step and left them derived from an
older tip. It showed as `4 insertions, 3 deletions` in the numstat — law 11's
*"read it as arithmetic"*, working exactly as written. Re-derived and now `4 / 0`
in all eleven.

## What this lane did NOT build, and why

* **The capture screen's two inputs** — the capture-wizard lane owns
  `ServiceRequestCapturePage.tsx` this wave. ⚠ **That screen still tells a clerk
  the licence is not recorded**, because its `driversLicenceReason` falls back to
  the catalogue sentence when the server stops declaring it unavailable. **Three
  things must go in that lane's commit:** `UNAVAILABLE.driversLicence` in
  `serviceRequestShared.tsx`, the `driversLicenceReason` fallback, and the
  catalogue key `customers.serviceRequest.applicant.driversLicenceAbsent`.
* **The kind selector** (`applicant_kind`) — the control is the capture lane's;
  the server-side refusal `BR-CUS-1022` requires is built here.
* **A matcher over a service request.** The evidence exists now;
  `suggest_customer_matches` still raises, and its stated reason was corrected
  the same day because the old one had expired. A `strong` tier moves **$150.00**
  (**$153.50** with interest), so it is a wave with its own proof.
* **`acting_for`** — still a stated absence tracking `DEF-638` 12.b.
* **`ssn`'s kind gate** — `DEF-CUS-5409`.
* **A future-date or plausibility check on the date of birth.** Deliberately
  absent: `customers.date_of_birth` has never carried one, and a check on one
  column alone would let the same date be accepted at the counter and refused on
  the request with nothing saying which surface is right.

## The browser walk — the only check in this repository that sees rendered output

Hard-won law 6. A lane-local PostgreSQL database (migrated, `seed_demo`, then one
seeded request carrying the worked example), Django on 127.0.0.1:18731, the built
SPA served by `server.mjs` on 18732, Chromium at **1440 and 1280**, signed in as
the demo utility's own admin. Both servers stopped and the database dropped
afterwards.

**What the applicant panel of `SR-26-0001` actually draws, at both widths:**

```
SOCIAL SECURITY NUMBER      DRIVING LICENCE            DATE OF BIRTH
••• ••• • 4471              •••• 4882                  03/14/1988
 · stored encrypted          · stored encrypted
```

`ACTING FOR` still reads *"Whether somebody is applying for themselves or for
another person is not recorded on a request yet"* — the one absence that is still
true.

**Asserted on the RENDERED text, not on the payload**, at 1440 and at 1280:

| | 1440 | 1280 |
|---|---|---|
| the page contains `TX-1234882` / `TX1234882` / `1234882` | no | no |
| the page contains `452-88-4471` / `452884471` | no | no |
| shows the licence's last four `4882` | yes | yes |
| shows the SSN's last four `4471` | yes | yes |
| shows the date of birth `03/14/1988` (the tenant's regional format, not the ISO string) | yes | yes |
| says *stored encrypted* | yes | yes |
| still says the licence is *"not recorded anywhere yet"* | **no** | **no** |

**Screenshots for the Product Owner**
`/tmp/…/scratchpad/lane-G-shots/laneG-request-detail-applicant-1440.png`
`/tmp/…/scratchpad/lane-G-shots/laneG-request-detail-applicant-1280.png`

⚠ **THE CAPTURE SCREEN WAS NOT WALKED AND ITS TWO INPUTS ARE NOT THERE YET** —
that screen belongs to the capture-wizard lane this wave. The walk above is the
READ side, which is the half this lane owns.

## Reds not caused by this lane, dated

* **`G44 display-truth` names `ServiceRequestDetailPage.tsx:747`** — a
  `{line.quantity}` in the fees table. `git log -S 'line.quantity' --` dates it
  to **`f6fa3670`**, *"customers(S21): render the drawn UNIT group on the account
  Overview"*. Not this lane's; not touched.
* **`G38 stated-absences` was DOWN 65 → 58 and therefore RED.** One of the seven
  is this lane's (`drivers_licence_absence`); the other six are the wave's other
  lanes. The baseline is lowered to 58 to bank the measurement, with that split
  recorded in the gate's own file. Its sibling `date_of_birth_absence` is NOT
  part of the drop — it cited `DEF-638` and was in the TRACKED bucket.
* **`makemigrations --check` reports drift in `rating`** (`ck_discount_versions_scope`
  removed and re-created). Not `customers`, not touched.
* **`ruff` reports 2 errors in `apps/customers`**, both outside every file this
  lane edited (`selectors.py`, a repeated `"created"` key literal).
* The remaining gate failures name portal, work, runbooks, billing and metering
  files this lane never opened.

## The CHANGELOG sentence (not written here — the orchestrator owns step 7)

> A service request now records the applicant's date of birth and driving
> licence. The licence is stored encrypted and shown as its last four characters
> only, exactly as the Social Security number already was; the date of birth is
> stored as an ordinary date so it can be compared. Together they are what let
> the product recognise a returning customer from an application, which the
> signed rule has asked for since 25 August and no request could satisfy.
