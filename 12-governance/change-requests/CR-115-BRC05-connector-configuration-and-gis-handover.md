# CR-115-BRC05 — Connector configuration, the Ann Arbor GIS handover, and the state of play

**Raised:** 2026-09-17 · **Branch:** `claude/gifted-johnson-top7zn` · **Requester:** Product Owner, in the working chat session

> **⚠ WHY THIS FILE EXISTS.** The PO asked for the day's decisions and the lane
> state to be written into the repo *because the session was running out of
> context*: **"can you write all these details in CR - our token are going to
> cmplete"**, then **"commit all work and stop all lanes"**. Hard-won law 9 and
> law 10 — the conversation does not survive, the repo does. Everything below was
> ruled in chat on 2026-09-17 and some of it is recorded **nowhere else**.
> A reader should treat this as the handover note for whoever picks the work up.

---

## 0 · Status at handover

All lanes were **stopped by instruction**, mid-flight. Four of six had not pushed.

| # | Lane | State when stopped | On the branch? |
|---|---|---|---|
| 1 | **One URL path** — collapse the three resolvers into one | running ~50 min; was at "the existing suites — the regression proof" | **NO — work lost** |
| 2 | **Run now** (+ the per-API table that was to follow) | running ~1 h; was at "now the gates, through the registry path" | **NO — work lost** |
| 3 | **Per-API table and form** | ✅ **DONE 2026-09-17, `2.296.0`** — §7 built end to end: the closed Kind list, the Add form (Name · Kind · URL, **no field mapping, no key**), the Edit and Delete row actions, the Enabled switch on ours and theirs, and all five rules of §7.5 with their reasons in the code. `BR-INT-078` is the rule; `integrations/0014` the table, with RLS FORCE in the same migration. Walked in a browser end to end — `10-scripts/cr115_custom_apis_walkthrough.mjs`, 7 steps, 31 assertions, 0 page errors. ⚠ Two defects found BY CLICKING and fixed (`DEF-INT-5683` the list served on the wrong payload so `+ API` was never drawn; `DEF-INT-5681` the set-up screen's *All use the address above*). ⚠ Per-API KEYS deferred on §7.6's own instruction — `DEF-INT-5680`. | **YES** |
| 4 | **GIS browser walk** | completed | **YES — `d9dc60df`** |
| 5 | **Second Invoice Cloud connector** | pushed as it was stopped | **YES — `6f7dabf4`, 2.291.0** |
| 6 | **Fix what the GIS walk found** | running ~10 min; reported **disk at 228 MB free** and was reclaiming worktrees | **NO — work lost** |

⚠ **Lanes 1, 2 and 6 must be re-run from their briefs below. Nothing of theirs survived** — only what is pushed survives in this environment (law 12).

⚠ **DISK PRESSURE IS REAL.** Lane 6 reported 228 MB free and was clearing stale
worktrees when stopped. `df` showed 6.1 G on `/` afterwards. A lane that cannot
write cannot push. Clear abandoned worktrees before dispatching more lanes.

### Shipped today, on the branch

`2.287.6` tenant isolation (four integrations reads now name the utility, + `G126`) ·
`2.288.0` connector grid → table · `2.288.1` connector view screen header/KPIs/actions
+ the Edit save path · `2.289.0` Invoice Cloud partner API · `2.289.1` · `2.290.0`
GIS foundation (CR-112) · `2.290.1` the `url` field kind + allowed-addresses warning ·
`2.290.2` the State column means the connector · `2.291.0` **two Invoice Cloud
connectors** so a key can be issued.

---

## 1 · Rulings of 2026-09-17, verbatim

Every one of these was given in chat. Where a ruling was later narrowed, **both
statements are kept and dated** — a record of what was ruled at a moment is
evidence, and editing it to match a later clarification stops it being evidence.

### 1.1 The connector table (CON-01)

| # | PO, verbatim | Reading |
|---|---|---|
| R1 | *"we are overriding the deciion and converting it form Grid -> Table - table only"* | overrides the blueprint, which considered a table and declined to draw one |
| R2 | *"Action im looking for - Connect, View, Edit, Keys- based on this status will chnage"* | four actions, always present, enablement varies |
| R3 | *"this is good - please add it"* | ratifies the seven-row matrix **with its greyed reasons**, which is what was shown |
| R4 | *"Im good with these columes - please implment it"* | the ten columns |

**Tooltip strings are ruled, not paraphrasable:** *"Not connected yet"* ·
*"Already connected"* · *"Not built yet"*.

### 1.2 The connector view screen (S142)

| # | PO, verbatim |
|---|---|
| R5 | *"actions on this screens - should be on top - like we follow as per our ui guideline"* |
| R6 | *"you did not inlcude rEgenerate Keys button"* |
| R7 | *"we did not include any KPIs line"* → the four tiles, then *"this is good"* |
| R8 | *"thi sis okay"* (the four body panels — no change) |
| R9 | *"please go ahead and fix this"* (the finished spec) |

**Two of these override the drawing and are recorded as overrides:** the blueprint
puts the actions in a FOOTER at the bottom and draws NO KPI line.

### 1.3 Allowed addresses

| # | PO, verbatim | Note |
|---|---|---|
| R10 | *"In fact we dont want allowed_addresses - restriction - can we make it options"* | |
| R11 | *"pls fix this"* — said **after** being told, in plain words, that with no addresses listed the key alone is the whole door and anyone holding it can call from anywhere | **the consequence was shown before the ruling; that is what makes it a signature** |
| R12 | *"a) A short line under the field when you clear it — \"This allows any address.\" - yes okay"* | only on non-empty → empty |

⚠ **Two sentences now sit under the cleared box** — the grey *"Leave blank to allow
any address."* and the red *"This allows any address."* Both were PO-ruled hours
apart. **Collapsing them was put to the PO and NOT answered.** Open.

### 1.4 Invoice Cloud

| # | PO, verbatim | Reading |
|---|---|---|
| R13 | *"company_id = Keys will esnure it map to tenant ID"* | superseded by R17 |
| R14 | *"I want to use batch run to take payment feed from Them - not online updates"* | no partner payment POST |
| R15 | on a partner waiving a late fee: *"no"* | `late_fee_waived` not honoured |
| R16 | on overpayment → credit note on their say-so: *"yes"* | `create_credit_note` honoured |
| R17 | *"you will ahve to remove company ID filter from all Apis - we cannot tell tenant ID outside our system"* | **supersedes R13 and the PO's own 2026-09-16 *"company_id = tenant id"*** |
| R18 | *"no this is not there - we will call htheir APis - we will ahnel those APis seperately - rember Invoice Cloud is both direction"* | **narrows R14 the same day: there is NO FILE.** We dial their API on a schedule |
| R19 | *"a) Two connectors ... - this is correct - we ahve to issue our key and also save secrete given by them in bi directional Connectors"* | two connectors NOW; **one connector holding both credentials is the standing requirement that is still owed** |

**Our judgment, recorded as ours (law 13), not put to the PO:** when a feed row says
a late fee was waived AND carries a real payment — **post the payment, leave our late
fee standing, flag the row for a clerk.** Refusing loses money a consumer really paid;
honouring lets a partner cancel our charge, which R15 forbids.

**Answers to the six questions put to the PO:**
ids travel as our text unchanged · `remote_plan_id` = the account's rate plan,
**`consumer-info` only** · `projectType` is the literal `"Utility Billing"`, **not
derived** · `remote_utility_id` **echoes what they sent**, omitted when they sent
nothing · `additional_data.payment_received` **UNANSWERED — `OQ-INT-12399`, key
absent from the payload** · the payment file **does not exist** (R18).

### 1.5 Ann Arbor GIS

| # | PO, verbatim / ruling | Note |
|---|---|---|
| R20 | Map tiles: *"We dont need this right now"* | out of this wave; the field stays, unused |
| R21 | A separate seeding job: *"we dont need this"* | address search does the job |
| R22 | *"We will need to use 2 · Address search ... at first time to map pacle ID and Point ID during first run or when we create the premsies and Unit first time - that the answer to find out mathcing keys"* | **search is IN, and it is how both keys arrive** |
| R23 | *"please ensure you dont call ArcGis Apis for every Premsies or unit again and again - they might return you all the gis ids from there tbale in 1 go - these can be uptp 70,000 ... and against thse format match in loop with our premsies and units"* | **one paged pull, one snapshot, match locally.** Changed the design from ~8,000 calls to ~50 |
| R24 | City unreachable while creating a premises: **(b)** let them type it, mark **unverified**, the sync fixes it later | |
| R25 | A building with no point of its own: **(a)** leave its pin blank | never borrow a unit's, never average |
| R26 | *"if we had a parcel ID and it does not match becuase of split - in such case you will have to use address matching and look for new parcel ID"*, confirmed again for the merge case | **a key that stops resolving is re-derived by address search; one clean match applies it, anything else waits for a person** |
| R27 | A City address we have no premises for: **(c) ignore** | not even a work item |
| R28 | Default disposition per field: **(c) never touch by default** | ⚠ so the first runs change NO addresses — the report must say *"N differences found, 0 applied"* or it reads as broken |
| R29 | *"it is city problem our job is the keep parcel ID updated - we dont need to - we dont inform city"* | we do not report data problems to the City |
| R30 | The URL field: **(a) build it now with the Edit fix** | shipped in 2.290.1 |

**The Ann Arbor service address, for the record:**
`https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/SEUQualifiedAddress/FeatureServer/0/query`

**The data mapping, as ruled:** `PIN` → `premises.gis_parcel_id` · `FULLPIN` →
`unit.gis_point_id` · `Street` (or the six components assembled) → `premises.address_line` ·
`City`/`State`/`Zip` → premises, **Zip kept as TEXT** · `Unit` → `unit.label` ·
`Point Y`/`X` → the **unit's** lat/lng; the **premises'** only from the point whose
`Unit` is empty — **no averaging** · `Status` → `gis_status` · plus `gis_verified`/
`gis_verified_at` and the replaced-key history.

### 1.6 Per-API configuration (the work that was NOT finished)

| # | PO, verbatim | Reading |
|---|---|---|
| R31 | *"i dont have Run button here"* | Run now, with `started_by` (schedule\|person+name) and `mode` (**preview**\|apply). **Preview writes nothing at all** |
| R32 | *"here Customer is giving custom URLs - when we read ... they can give one or more URls to call. hence we need a form to add them"* | |
| R33 | *"as product for Arc GIS we might have already 5 to 10 we read pAIs thata re configured in our product, so we offer those also as standard ... for us Cusmization efforts will reduce"* | the business reason |
| R34 | *"any every custom APis for that customer - we wil ahve to write a code to exeucte business logic for that - which is another issue that we have to handle - using runbook"* | **a custom API is a business-logic problem, and this product's place for business logic is a Runbook** |
| R35 | *"DOnt add field Mapping here - remove it"* | **removed by the PO, not forgotten.** Do not restore it |
| R36 | *"in table also give edit button + remember if we have existing Apis , standard APis those will be availabel for enable diable but those will not be editable"* | |

**The reading that reconciles R32/R33/R34 — record it as a reading:** the dropdown
is **what KIND of call this is** (our closed list), the **name is theirs**. Nothing
addable can lack code behind it, and a genuinely new kind of call is a Runbook.

**The form:** Name (theirs) · Kind (Address lookup · Scheduled sync · Map tiles) ·
URL (theirs) · Key (optional) · **Add**. **No field mapping.**

**The table:** Name · Kind · URL · Key · **Enabled** · **Edit**.

| | Standard (ours) | Custom (theirs) |
|---|---|---|
| Arrives | with the connector | via the form |
| URL | the connector's Service address | its own |
| **Editable** | **no** | yes |
| Enable/disable | yes | yes |
| **Delete** | **no** | yes |

**ONE Scheduled sync per connector** — a second is REFUSED at the form **and on the
server**. Reason, which must be in the code or it reads as arbitrary: a sync WRITES,
so two pointed at two layers both update the same premises and the last to run wins
silently. Extra customer reads are **lookup-only**; Address lookup **merges** every
enabled URL and ranks together.

**A disabled API is NOT scheduled and NOT called** — otherwise the switch is
decoration (law 2's mirror). *Working N of M* and the State word count **only
enabled**, without undoing `DEF-INT-5597`.

**Known limit, written down rather than designed around:** a customer with TWO
address layers cannot add the second themselves. The answers are a manifest line
from us (one file, no screen code) or a Runbook. There is no third.

---

## 2 · What the GIS browser walk found (`d9dc60df`)

The first time anything about CR-112 was seen on a screen. Script:
`10-scripts/cr112_city_address_keys_walkthrough.mjs` — it prints the bundle and
backend it used and names the **false-pass mode for every step**.

> **Can a clerk in Ann Arbor create a premises today and have it carry the City's
> keys? NO** — for two independent reasons.

⚠ **THE CITY WAS NEVER REACHED.** `curl` → code `000`; inside Django,
`OSError: Tunnel connection failed: 403 Forbidden`. A local stub was used.
**This proves our code and says nothing about Ann Arbor's data.**

| id | sev | what |
|---|---|---|
| `DEF-INT-5599` | high | an unreachable City is a **500**, not the ruled refusal. The breaker counts nothing (`consecutive_timeouts=0` after four failures) so it never opens; the amber *"The City is not answering"* box can never be shown; **the panel vanishes as the clerk types, taking their typed text with it** |
| `DEF-INT-5600` | high | the **address-point id never reaches the form** — `units.gis_point_id` is NULL on every property, permanently. The screen draws *"Point — No point yet"*, which reads as a fact about the property rather than a missing capability |
| `DEF-INT-5601` | high | `gis_parcels`/`gis_layer`/`gis_match`/`gis_search` — **2,044 lines, no caller** outside their own tests |
| `DEF-INT-5602` | med | `premises.gis_status` always NULL — `payload_from` reads a key `candidate_from` never sets |
| `DEF-INT-5603` | med | list truncated at **8** with no notice under *"8 matches from the City's records"*; cap enforced (8) ≠ cap documented (20) |
| `DEF-MET-5604` | high | *"Change these"* accepts parcel/lat/lng, answers **201**, writes **none** of them; and *"✓ Found on the city map"* is **unconditional** — a green tick over three *"not yet"* rows |

**What does work:** hard rule 8 holds (the address is on the premises; `units`
declares no address column — asked of `information_schema`, not of the values) ·
the freehand fallback marks the row `gis_unchecked = true`, so R24's **data** half
is honoured and its **telling** half is not · a parcel another property already
holds is refused in words.

⚠ **A CLAIM THAT WAS NOT TRUE:** an earlier report said the backend groups
candidates and only the front end lagged. **It does not** — `gis.py::search`
returns a flat list and never calls `gis_search`. A lane trusting that note would
rewire the screen to consume groups the endpoint has never sent.

---

## 3 · The three regression risks, named by the PO

| # | | Why |
|---|---|---|
| 1 | **The Edit / save path** | it refuses field names it does not recognise — that is what broke the PO's allowed addresses (`DEF-INT-5579`–`5582`). The per-API rows go through the same route. **Prove a save in a BROWSER, not with a passing test** |
| 2 | **The endpoint column** | a fourth URL source is exactly how it went blank on every connector before (`DEF-INT-5502`), and how the wrong host reached a browser page policy (`DEF-INT-4259`). **This is why lane 1 exists and must be re-run first** |
| 3 | **The GIS nightly sync** | built assuming one URL per connector; must ask the per-API row first |

---

## 4 · Open, and owed

| What | Where |
|---|---|
| **`connection.status` never moves on a failed RUN** — only on an explicit test, connect, credential change, or the breaker (which counts silence only). **A connector tested once and failing nightly since still reads *Working*.** Three options put to the PO; **unanswered** | `DEF-INT-5598` |
| **How we recognise a payment already taken** on a scheduled pull — there is no file to hash. **Routed to Invoice Cloud, not the PO.** Nothing may WRITE a payment from `fetch_payment` until answered | `OQ-INT-12396` |
| `additional_data.payment_received` — three readings, three different numbers | `OQ-INT-12399` |
| One connector holding BOTH credentials (R19's standing requirement) | `DEF-INT-5574` |
| Collapsing the two sentences under the cleared address box | §1.3 |
| **50 of 128 gates failing**, *0 newly failing* — the standing set. Several are true findings hiding in a crowd | offered, not authorised |
| The PostgreSQL savepoint proof for CR-112 | `tests/test_cr112_gis_parcels_pg.py` — skips silently under the pinned settings; needs `DJANGO_SETTINGS_MODULE=config.settings.local` + `JOBS_EAGER=false` |
| **One real call to Ann Arbor's layer** — only the PO's deployment can reach it | blocks nothing in code; validates four assumptions |

---

## 5 · Process notes worth keeping

- **`tests/test_us_int_042_gis.py` = 42 passed** on the tip (run by the session, not a lane).
- **Baselines for "is this red mine?":** full gates **76 PASS / 50 FAIL / 2 SKIP**,
  *0 newly failing*; front end **11 files / 30 tests** failing at `53b8f303`, proved
  identical at its parent. **Compare by NAME, not by count.**
- **The shared checkout's defect register was a loaded revert** when the lanes were
  stopped: five rows (`DEF-INT-5605`–`5609`) appended to a base predating
  `DEF-INT-5599`–`5604`. `git diff --numstat` read **5 6** — five added, six gone.
  Every ordinary check passes on that. **Read the numstat as arithmetic.**
- **Four id collisions today**, every lane's arithmetic correct; what was wrong was
  *which world the maximum came from*. `allocate.py --verify` at push time is the
  only thing that caught them.
- **This CR's index row in `12-governance/11-change-requests.md` is OWED** — it was
  not written, deliberately, to avoid touching a shared register while lanes held it.


---

## 6 · HOW TO RESTART — briefs for the three lanes whose work was lost

Dispatch these in this order. **Each lane: its own `git worktree` under the
scratchpad, push with `10-scripts/push_paths.sh`, `ls 10-scripts/` before writing
any helper, and re-derive every blob AND every allocated id from the pinned tip at
push time — unconditionally, never inside a conflict branch.** Clear stale worktrees
first; disk was at 228 MB free when the last lane was stopped.

### Lane 1 — ONE PATH DECIDES AN API'S URL *(do this first; the others build on it)*

A **de-risking refactor with NO behaviour change.** An operation's URL is decided in
at least three places and a fourth is about to be added.

Known participants — **verify, do not trust this list**: `Operation.host_field`
(`registry.py` ~line 542, default `"base_url"`; `map_tiles` on `gis_esri` declares
`host_field="tile_url"`) · `selectors.host_fallback_field` (falls back to the
manifest's single field of kind `host` **or `url`** — `ADDRESS_FIELD_KINDS` — and
answers `None` when there are two, deliberately, per `DEF-INT-4259`) ·
`OperationRow.endpoint` on the wire, which the ENDPOINT column renders. **Find what
the RUNNERS actually use when they place a call** (`runners/fetch.py`, `serve.py`,
`deliver.py`, `adapters/gis_city.py`) — **if the screen and the call already read
different code, that is the finding and it matters more than the refactor.**

Build ONE function taking (manifest, operation, connection) returning the resolved
address **and how it was decided** — its own field, the connector's, or a fallback.
The provenance is required: the per-API work must show a clerk *"using the
connector's address"* vs *"its own"*, and a screen re-deriving that is a second
source by another name.

**Prove no behaviour change by enumerating every connector and every operation,
printing the resolved address before and after, and diffing. An empty diff IS the
deliverable.** A moved row is either a bug you found or one you introduced — stop
and say which.

Add a gate that refuses a second resolver, modelled on `G126`, zero-tolerance, with
a self-test proving it bites. **Prove it RED through `run_gates`' registry path,
never `python3 <module>`** (`DEF-GOV-3733`). Ask: *what would make this pass
wrongly?* — a gate grepping for a function name passes over an inlined copy.

**Do NOT add the per-API URL.** Leave the seam and say in the docstring where that
branch goes.

Browser check (law 6): `gis_esri` (two address fields, one operation on the second),
`email_smtp` (a `host` that is NOT a URL and must stay that way), and one ERP —
confirm the ENDPOINT column shows what the function returns.

### Lane 2 — RUN NOW, then the PER-API TABLE AND FORM

**Push Run now on its own first.** It depends on nothing here.

**Run now** (R31): a control on S142 for a connector declaring a scheduled fetch,
offering **Preview** and **Apply** — not one button that does the dangerous thing.
Every run records `started_by` (schedule \| person + name) and `mode`. **Preview does
everything and writes NOTHING — not the keys, not the fields.** Expose the route if
there is none (`CR-112` reported *"callable and tested, not yet exposed"*). Link to
where the reconciliation queue surfaces, or say why you could not.

⚠ **B14 rule 2 and the ratified header set** (Edit · Keys · Disconnect · Regenerate,
2026-09-17) — Run now must not silently become a fifth. If the honest home is the
operation's own row, **make that case** rather than forcing the header.

⚠ **`DEF-INT-5601`: the thing the button calls has no caller today** — 2,044 lines,
never invoked outside its own tests. Budget for that.

⚠ **R28 means the first runs change no addresses.** The report must say *"N
differences found, 0 applied"* with the reason, or a clerk files a defect against
correct behaviour.

**Then §1.6's form and table**, built as ONE BRANCH inside lane 1's function.
Check for lane 1's commit first; if absent, push what you have and say so — do not
build a fourth resolver, and lane 1's gate will refuse one.

Storage must survive the manifest-driven validation that refuses unknown field names
(`DEF-INT-5579`–`5582`). A key is a CREDENTIAL, not config — if per-API keys need
the credential store changed, **ship URL + Enabled without them and say so**; Ann
Arbor needs no key at all.

### Lane 3 — FIX WHAT THE GIS WALK FOUND

Maintenance process: **REPRODUCE in a browser before reading code**, LOCATE the file
actually mounted, BLAST RADIUS both ways. Read
`10-scripts/cr112_city_address_keys_walkthrough.mjs` first; **re-run it before and
after and quote its verdict lines both ways** — the thing that found the defects is
the thing that must change its mind.

Scope: `DEF-INT-5600` (start at `adapters/gis_city.py::candidate_from` and follow the
value to the form) · `DEF-INT-5599` (`gis_city.py::_call` catches `TimeoutError` and
nothing else, so a refused connection is re-raised by `guarded_call` as *"an answer,
even an unhappy one"* — which it is not; and `FindTheAddress.tsx` maps any non-409 to
`absent` and returns `null`) · `DEF-MET-5604` (**the false green tick is the worst of
these — make it conditional on a real key or remove it**) · `DEF-INT-5602` ·
`DEF-INT-5603`.

**NOT in scope:** `DEF-INT-5601` — lane 2 owns giving it a door. Do not build a caller.

If you borrow the tenant's `gis_esri` `base_url` for a stub, restore it in a
`finally` and fail loudly if you cannot — that went wrong once and left a live
connector pointed at `127.0.0.1`.

### Also queued, unauthorised

**The standing red.** 50 of 128 gates failing, *0 newly failing*; front end 11 files
/ 30 tests. Several are true — a hold that outlived its screen, a citation pointing
at nothing, a screen not matching its drawing. They are invisible in a crowd of 50.
One lane: fix what is real, retire what is stale. **Offered to the PO twice, never
authorised.**

---

## 7 · CUSTOM URLs ON A CONNECTOR — THE FULL SPECIFICATION

**Ruled by the Product Owner on 2026-09-17 in the working chat session, and written
here the same day.** §1.6 above captured this work from the rulings as they
arrived and is NOT superseded — it is the same subject at less detail. **This
section is the specification; where the two differ in detail, this one is later
and wins.** Quotes are verbatim.

### 7.1 · Why it exists

> *"here Customer is giving custom URLs - when we read - and we will ahve to
> accomodate that - they can give one or more URls to call. hence we need a form
> to add them ; At the same time, as product for Arc GIS we might have already 5
> to 10 we read pAIs thata re configured in our product, so we offer those also
> as standard to customer. now when we have on and off button - it allow them t
> chose how much theywant to use; for us Cusmization efforts will reduce"*

**The business goal is REDUCING CUSTOMISATION WORK.** Every layer a customer can
point us at themselves is a release we do not have to cut. That is the measure
this feature is judged by, and it is why the closed Kind list below is a
constraint on US rather than on them.

### 7.2 · The rule that makes it safe — AND IT CORRECTS AN EARLIER, BROADER ONE

⚠ **AN EARLIER RULE SAID ADDING AN API IS OURS AND NOT A CLERK'S**, on the
reasoning that a URL with no code behind it does nothing. **THE PRODUCT OWNER
RULED THAT TOO BROAD, AND THE CORRECTION IS THE WHOLE DESIGN.**

The distinction is the connector, not the customer:

* a **PROTOCOL READER** — our Esri connector knows how to query an ArcGIS layer
  and map its fields, and **does not care WHICH layer** — needs **no new code**
  for a customer's extra URL;
* a connector whose **every API is bespoke** still falls under the old rule.

**THE RECONCILIATION, AND THE LINE THE WHOLE DESIGN RESTS ON:**

> **THE KIND IS OURS. THE NAME IS THEIRS.**

A clerk picks what SORT of call this is from a closed list we ship, and gives it
their own name and their own URL. **Nothing addable can lack code behind it.**

> *"any every custom APis for that customer - we wil ahve to write a code to
> exeucte business logic for that - which is another issue that we have to handle
> - using runbook"*

So **a genuinely new KIND of call is a Runbook, not a form field** — a URL alone
cannot express what to do with the answer.

### 7.3 · The form

| Field | |
|---|---|
| **Name** | theirs — *"Zoning layer"*, *"Address points"* |
| **Kind** | **closed list, ours**: Address lookup (while you wait) · Scheduled sync (nightly) · Map tiles |
| **URL** | theirs |
| **Key** | optional |
| **Add** | appends to the table |

> *"DOnt add field Mapping here - remove it"*

⚠ **NO FIELD MAPPING ON THIS FORM. Removed by the PO BY NAME, not forgotten. Do
not reintroduce it, do not add a smaller version, do not make it a link.**
⚠ **AND IF A SCHEDULED SYNC PROVES UNUSABLE WITHOUT ONE — SAY SO AND STOP.** The
product has a mappings screen and that is a SEPARATE DECISION, not this lane's to
take. Solving it quietly inside this form is the failure this clause exists to
prevent.

### 7.4 · The table

Columns: **Name · Kind · URL · Key · Enabled · Edit.** Ours and theirs in ONE
list, ours marked as standard.

> *"in table also give edit button + remember if we have existing Apis , standard
> APis those will be availabel for enable diable but those will not be editable"*

| | Standard (ours) | Custom (theirs) |
|---|---|---|
| How it arrives | ships with the connector | added through the form |
| URL | the connector's Service address | its own |
| **Editable** | **NO** | yes |
| Enable / disable | yes | yes |
| **Delete** | **NO** | yes |

⚠ **AN API ALREADY CONFIGURED DROPS OUT OF THE DROPDOWN — one configuration per
API, never two.**

### 7.5 · The five rules the behaviour must obey

**Each reason belongs IN THE CODE, or the rule reads as arbitrary and the next
lane simplifies it away.**

| # | Rule | Reason |
|---|---|---|
| 1 | **ONE Scheduled sync per connector.** A second is refused **at the form AND on the server**, in words a clerk can read | a sync **writes**. Two pointed at two layers both update the same premises and **the last to run wins silently**. ⚠ **A form-only rule is a rule until someone calls the API directly** |
| 2 | **Address lookup MERGES** — search every enabled lookup URL, merge the candidates, **rank them together** | a city with a qualified-address layer AND an address-points layer just works. ⚠ **The ranking already exists in the backend** — find it, do not rebuild it |
| 3 | **A disabled API is NOT scheduled and NOT called** | otherwise the switch is decoration — hard-won law 2's mirror. **A switch that renders and changes nothing looks identical to a working one** |
| 4 | ***Working N of M*** and the **State** word count **ONLY ENABLED** APIs | a switched-off API must not drag the count, and a connector is not *Not working* because of one you turned off |
| 5 | **Do NOT undo `DEF-INT-5597`** (`2.290.2`) | the State column means the **connector**, never one of its APIs |

### 7.6 · Storage constraints — read BEFORE choosing where these rows live

* **The save path refuses field names it does not recognise.** That is what broke
  the PO's allowed addresses — `DEF-INT-5579`–`5582`. The new rows go through the
  same route. ⚠ **Prove a save works in a BROWSER, not with a passing test.**
* **A key is a CREDENTIAL, not config.** Today a connector holds ONE credential,
  stored encrypted, separately, shown once. Several per connector touches the
  credential store, *Keys in use*, rotation and expiry. ⚠ **If per-API keys need
  that changed, ship Name / Kind / URL / Enabled WITHOUT them and say so** — Ann
  Arbor needs no key at all, so a per-API key would ship **untested against any
  real vendor**.
* **The rows are PER UTILITY** — they sit on the **connection**, which is already
  tenant-scoped. Two utilities on the same connector configure it independently.

### 7.7 · The URL resolution trap

There are already three ways an operation's URL is decided — its own declared
field, the connector's address, and a fallback. **The per-API URL must be ONE
BRANCH inside a single resolution function, never a fourth lookup.**

**It has cost twice:**
`DEF-INT-5502` — the endpoint column rendered **blank on every connector we
ship** · `DEF-INT-4259` — **the wrong host reached a browser page policy**, and
the City's own map server would have been blocked.

⚠ **THIS IS NOW DONE AND IS NO LONGER A WARNING TO HEED BUT A FILE TO USE.**
§6 lane 1 landed as `3ebf779cc`: `06-backend/apps/integrations/addressing.py`
collapses what turned out to be **SEVEN** resolvers, not three, and reports its
provenance on the wire as `endpoint_source` / `endpoint_field`. **`G128` refuses
a second resolver** and is deliberately not a grep for a function name, because
an inlined copy has no name to grep for and inlining is how all seven arose.
The provenance is **required**: the view screen must tell a clerk WHICH address
they are looking at, and **a screen that re-derives it is a second source by
another name.**

### 7.8 · The known limit — WRITTEN DOWN, NOT DESIGNED AROUND

**A customer with TWO address layers cannot add the second themselves**: the Kind
list is closed and each of our APIs takes one configuration. The honest answers
are **a manifest line from us** (one file, no screen code) or **a Runbook**.
⚠ **There is no third, and it must not be invented.**

### 7.9 · Run now, which ships alongside

> *"i dont have Run button here"*
> *"you build it and allo me to do a manula trigger based on parameters - so
> using parameter we can differentiate whter it si schedule job or it is manual
> call"*

**The two parameters are the PO's own framing, not our invention:**

| Parameter | |
|---|---|
| `started_by` | `schedule`, or **person** with their name |
| `mode` | `preview` or `apply` |

**Preview does everything and writes NOTHING — not the keys, not the fields.
Report only.**

⚠ **THE FIRST RUNS WILL CHANGE NO ADDRESSES AT ALL**, because the PO ruled
*never touch by default* for every mapped field (R28). **The report must say
*"N differences found, 0 applied"* with the reason**, or a clerk files a defect
against correct behaviour.

⚠ **`DEF-INT-5601`: the thing the button calls — 2,044 lines across four modules
— has no caller today outside its own tests.** Budget for that.

⚠ **B14 rule 2 and the ratified header set** (Edit · Keys · Disconnect ·
Regenerate, ruled 2026-09-17): **Run now must not silently become a fifth.** If
its honest home is the operation's own row, **make that case** rather than
forcing the header.

### 7.10 · Proof required

> ✅ **DONE 2026-09-17 (`2.296.0`).** Every line below was walked. The walk is
> `10-scripts/cr115_custom_apis_walkthrough.mjs` — 7 steps, 31 assertions, no
> page errors and no 5xx — and it RESETS ITSELF, because the first run's own
> *Address points* row made `Address lookup` drop out of the dropdown (§7.4
> working exactly as ruled) and the second run read that as a broken form.
> ⚠ **Rule 3 is asked of the SERVER from the browser's own session**, not of the
> screen: with every lookup switched off, `GET …/address-search` answers
> `integrations.gis.lookup_off` and dials nothing. A screen can only draw what
> it was handed, and the question rule 3 asks is whether the code that PLACES
> THE CALL obeys the switch.
> ⚠ **Two defects were found by this walk and by nothing else** —
> `DEF-INT-5683` and `DEF-INT-5681` — after the backend was finished and every
> test was green. That is law 6 earning its place twice in one afternoon.


* **Law 6 — CLICK IT.** Add a custom lookup, see it in the table, **switch it off
  and confirm it is NOT called**. Try a **second Scheduled sync** and see it
  **refused in words**. **Edit a custom row; confirm a standard row offers no
  Edit.**
* **Ask of every check: what would make this pass WRONGLY?**
* ⚠ **The City of Ann Arbor is unreachable from the build environment** — `curl`
  returns code `000`, refused by the egress proxy. Build against `CR-112`'s
  stand-in, **whose own docstring says it is hand-shaped from documented field
  names and NOT a recording.** ⚠ **Nothing built here proves anything about Ann
  Arbor's real data. Say so plainly rather than letting a green run imply it.**
* **Locale copy through `10-scripts/i18n_fanin.py`, ALL ELEVEN catalogues, each
  in its own idiom** (B14 rule 35 — a catalogue is written in its own language,
  not translated from English).
