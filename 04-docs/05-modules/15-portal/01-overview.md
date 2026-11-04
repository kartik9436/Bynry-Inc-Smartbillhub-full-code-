# 15 · Customer Web Portal — module overview

**Module:** `portal` (product name: **Customer Portal**) · **Source:** `CR-068` ·
**Blueprint:** *SMARTBillHub Customer Portal · Blueprint, read of 2.125.4* (163 pages,
26 sections, read in full 2026-09-03) · **Docs module:** the fifteenth, following the
fourteen that exist.

## 1 · What this module is

A second front door onto the same tenant, with a much narrower key. It gets **no**
database of its own, **no** bills of its own and **no** second copy of a balance. It
reads what the staff app writes, through the same forced tenant isolation, and it may
write in **four places only**.

The blueprint's own sentence, and it is the whole security model:

> *"The portal is a key, not a system."*

**Today there is one kind of user in this product: staff.** Three fixed roles, all of
them employed by the utility. A customer has never signed in to anything. The customers
themselves are already on file — richly so — and what no customer record carries is a
password.

## 2 · The four write points, and nothing else

| The portal MAY write | The portal may NEVER write |
|---|---|
| **A payment** — one row, allocated by the utility's rule | **Anything on an issued bill** — immutable, for everyone |
| **A service request** — draft, submit, answer, withdraw | **Where a payment lands** — the utility's allocation rule decides |
| **A meter reading** — held for review, never billed directly | **A protection or a hold** — needs a person and a document |
| **A preference** — contact details, paperless, language | **Who the account belongs to** — that is a money decision |

⚠ **This table is the security model, not a scope note.** A portal built this way cannot
corrupt the books even if its authentication is defeated — the worst an attacker achieves
is a request a clerk refuses. `BR-CWP-001`–`BR-CWP-008` state it as law and `US-CWP-001`
carries the gate that proves it.

## 3 · Size

| | Count | Where it is written down |
|---|---|---|
| Specifications inherited from the blueprint | **56** (`CP-01`–`CP-56`) | `CR-068` §8 and the blueprint's §25 register |
| Screens | **79** — 14 guest, 54 signed-in, 7 back-office, 4 phone | §5 below, and `CWP-001`–`CWP-079` |
| Epics | **12** | `06-epics/` |
| User stories | **74** | `05-user-stories.md` |
| Business rules | **96** (`BR-CWP-001`–`BR-CWP-096`) | `02-business-rules.md` |
| Test cases | **≥ 4 per story** | each story's §3 |
| New tables | **14** | `03-field-map.md` |
| Changed columns on existing tables | **11**, across 6 tables | `03-field-map.md` |
| Endpoints | **98** — 14 guest, 71 portal, 12 back-office, 1 webhook | `07-endpoints.md` |
| End-to-end journeys | **18** | `04-flows.md` |
| Releases | **5** | §6 below |
| Open questions blocking code | **9** (`OQ-1391`–`OQ-1399`) | `12-governance/01-open-questions.md` |

## 4 · Who it serves — four kinds of person, ONE mechanism

The data model already joins a customer to accounts many-to-many, so a landlord holding
a master account over common areas while their tenants hold their own is **already
lawful**. The portal renders what the model permits and adds no second code path.

| Who | The 80% question | What makes them different |
|---|---|---|
| **Householder** — the 80% case | *What do I owe, and by when* | One account, arrives on a phone, may not have signed in for eleven months |
| **Landlord or manager** | *Which tenant's meter drove which bill* | One customer record, many accounts, possibly a master over common areas |
| **Business customer** | *An invoice my bookkeeper can file* | Identified by company name and tax ID. Wants downloads, not charts |
| **Authorised third party** | *Act for someone* | Not the holder. May see and pay, never close or re-own |

And a fifth person who is not a customer yet, wants to start service, and has no account
to sign in to. That journey begins **before identity exists** — `US-CWP-012` and
`US-CWP-045`.

⚠ **THE SESSION HOLDS A SET, NOT AN IDENTITY.** A portal session is a tenant, a person,
and a **set of (account, what they may do)** — never a customer id on its own. A
householder's set has one entry; a landlord's has four; a bookkeeper's has one that
expires. **And the set is FLAT.** A master account is one more entry in it, not a
parent, and it confers nothing over anybody else's account. The obvious implementation
is a hierarchy and the correct one is not — the blueprint draws the hierarchy crossed
out for exactly that reason (`BR-CWP-013`, `BR-CWP-014`).

## 5 · The screen families

| Family | Range | Count | What it is |
|---|---|---|---|
| Guest — no login at all | `CWP-001`–`CWP-014` | 14 | The widest door. Most people who touch a utility's website never sign in |
| Signed in | `CWP-015`–`CWP-068` | 54 | Six tabs behind one shell |
| Back office — **STAFF screens** | `CWP-069`–`CWP-075` | 7 | ⚠ These live in the STAFF app's Settings, not the portal |
| Phone | `CWP-076`–`CWP-079` | 4 | Newly numbered by this module — see §8 |

⚠ **`CWP-069`–`CWP-075` ARE NOT PORTAL SCREENS.** They are the back office *for* the
portal — the overview, branding, help answers, tips and service centres a System Admin
edits. They belong in `07-frontend/src/features/tenancy/` under Settings and carry `CWP`
numbers only because the blueprint drew them. **A lane that builds them into the portal
app has put a staff screen behind a customer login.**

## 6 · The five releases, each one launchable

Ordering is not preference — it follows what the product can already support, so the
first release ships against machinery that is finished and tested rather than waiting on
an integration.

| # | Release | What it launches | What must be built |
|---|---|---|---|
| **1** | **The public front** | A utility puts its portal live while everything below is still being decided | An interruption record and an affected-area rule · help content per tenant and per language · public reads for premises, services and prices · unauthenticated request creation behind the anonymous throttle · the five per-tenant switches |
| **2** | **See everything, pay nothing** | Removes a large share of *"can you email me my bill"* calls | Customer credentials and sessions · one-time codes · **the balance read** · the portal shell |
| **3** | **Ask us for things** | Self-serve move-out, transfers, disputes, self-reads | The portal as a notification channel · a customer-submitted read and its review queue · customer-raised requests and disputes |
| **4** | **Help before it goes wrong** | A customer who can see the ladder and ask for a plan is better served whether or not money can move yet | Delegated customer users · customer-raised plans · the arrears view · the bill comparison |
| **5** | **Pay** | The promise the portal is named for | The gateway integration · the stored-instrument table · a live idempotent webhook · refunds to the original method |

**Help and answers ships with release 1, not after it** — the blueprint moved it there
itself, because the portal's help page is empty until somebody can write into it.

## 7 · What is already built, and it is most of it

The blueprint's central finding, and it is why this module is affordable:

| Already finished behind the counter | What the portal adds |
|---|---|
| Bills, lines, correction chains, the rendered PDF pinned to its issued template | A view |
| Payments, allocation, reversal, receipts, the books | A way to take the money (release 5) |
| Payment plans — preview, instalment arithmetic, activation, notices | A door for the customer |
| Level pay — eligibility, enrolment, re-levelling, settle-up | A screen. It is finished and hidden from the person it helps |
| The collections ladder, notice tiers, three protections with three different lifetimes | Words the customer can read |
| Read validation — high, low, rollover, window, estimation and true-up | One more source, through the **same** rules |
| The eleven-state service-request lifecycle, its document checklist and fee quoting | Four transitions and a customer-safe history |
| Eleven languages, with the template pinned including its language variant | Nothing |
| The anonymous throttle at sixty requests a minute | Doors behind it |

**And three things are genuinely missing, all of them named by the product itself:**
nothing publishes a **balance**; there is **no way to take a customer's money**; and the
notification catalogue lists *portal* among the channels this platform **does not have**.

## 8 · Step 0 — what moved under the blueprint, verified 2026-09-03

| The blueprint or `CR-068` says | Measured 2026-09-03 | Consequence |
|---|---|---|
| Blueprint headline: **79 screens** | **TRUE.** `G1`–`G14` (14), `P1`–`P54` (54), `B1`–`B7` (7), `M1`–`M4` (4) — every id present, no gaps | `CR-068` allocated **75** and stopped at `B7`. **The four phone screens had no numbers.** They are `CWP-076`–`CWP-079` here |
| `CR-068` §5: **56 specifications** | **TRUE.** `CP-01`–`CP-56`, no gaps | The register is the scope |
| Blueprint §25 closes: *"Thirty-eight rows, thirty-eight cards"* | **FALSE.** The table it closes has **56** rows | Off by eighteen, inside the one section whose job is listing seventeen count errors. **Build from the rows, never the sentence.** Filed |
| `CR-068` §9 screen titles | **FIVE ARE WRONG.** `CWP-013`/`014` and `CWP-060`/`061`/`062` carry titles taken from §16's *"where the customer meets it"* column, shifted by one | Corrected in `05-user-stories.md` §2. Filed |
| Blueprint: nine of thirteen questions ruled, **nine still open** | **TRUE**, once `PQ-13` is counted as answered by `CR-068` `R11` | `OQ-1391`–`OQ-1399` |
| Blueprint routes written as `pinehill.smartbillhub.com/…` | **FALSE, and the blueprint says so itself.** Tenancy is path-based since 2026-08-10 | All routes are `/{tenant}/portal/…`. `CR-068` `R11` |
| Read at **2.125.4**; `CR-068` written against **2.120.1** | Now **2.128.2** | Every *"as built"* claim in §7 above is `UNVERIFIED`. **The first hour of release 1 is checking them against the code** |

⚠ **NOT ONE SPECIFICATION STATUS IS VERIFIED, AND THAT IS THE BLUEPRINT'S OWN
INSTRUCTION:** *"A status guessed from a change log, or from a memory of having written
something, is worse than no status at all."* Several are expected to come back already
done, because a large part of this blueprint is a view over machinery that is finished
and simply has no screen in front of it. **That is a measurement, not an assumption.**

## 9 · What this module must NOT do — stated as prohibitions

1. **A portal credential must never resolve into a staff role.** Separate table, separate
   session, separate permission catalogue — **not one table with a flag on it.** The
   blueprint's reasoning: *"A defeated portal login then costs a customer's own data. A
   defeated shared login costs the utility's whole book."*
2. **The tenant is resolved before anybody is identified.** Path tenancy means a stranger
   can type any utility's name into the address bar, so the database is told which tenant
   it is working for **before** the question *"who is this"* is asked.
3. **The portal reaches the portal edge only.** A portal session must not call a staff
   route; the guest surface must not call the portal edge.
4. **No second copy of anything.** One set of services. The portal reads what the staff
   app writes.
5. **The four write points and nothing else.**
6. **A guest sees an amount and a status, never a person.** Holding a bill proves someone
   has the paper, not who they are.

## 10 · Where the rest of it lives

| File | What is in it |
|---|---|
| `02-business-rules.md` | `BR-CWP-001`–`BR-CWP-096`, and the 13 signed rules the portal inherits — **cited, never restated** |
| `03-field-map.md` | 14 new tables, 11 changed columns on 6 existing tables, and who owns each |
| `04-flows.md` | 18 end-to-end journeys |
| `05-user-stories.md` | The index: 74 stories, 12 epics, the screen map and the release each falls in |
| `06-epics/EP-CWP-01`…`12` | The stories themselves, in the canonical eight-section format |
| `07-endpoints.md` | 98 endpoints across four edges |
| `08-screen-layouts.md` | **One layout entry per screen, written while looking at its wireframe** — frame, template, regions, components |
| `09-component-inventory.md` | **The 24 components the 79 screens are built from, each defined once as Tailwind**, mapped to the staff kit and to B14 |
| `wireframes/CWP-###.png` | **The wireframe for every screen**, cropped from the blueprint — the reference to diff the running app against (hard-won law 6) |
| `10-execution-plan.md` | **The build order — five phases, eighteen waves (`A`–`R`), 105 tasks**, every one of the 74 stories placed in exactly one wave, each wave ending in a clicked demonstration and a version; verified against the code at `b29edecd` (its §0 lists where the documents and the code disagree, and the code wins) |

## The visual reference — this module's own pack, then r10 (PO 2026-09-03)

**PO, verbatim: *"for Cr68, 69 and 70 - you will have to ensure you refer to screenshot we build and not just r10"*.**
The layout, copy and state authority for this module's screens is **`wireframes/` in this folder** (76 images), read
through `08-screen-layouts.md` and `09-component-inventory.md`. **`05-prototype/r10` remains the default for every
screen the pack does not draw**, and for the shell and conventions a new screen inherits. **Where r10 and this pack
disagree on one of these screens, the pack wins** — it is the later drawing — and the divergence is stamped in
`08-screen-layouts.md` rather than followed silently. Diff the running app against the pack first (hard-won law 6).
