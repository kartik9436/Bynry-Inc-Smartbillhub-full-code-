# J44 — A delegate is invited, acts, and is named in the audit (*Common areas · See · Download · 30 Jun 2027 · Invited*, then an audit entry naming **Kestrel Bookkeeping**, not Maria Alvarez)

---
id: J44
tier: 2
rules: [BR-CWP-017, BR-CWP-009, BR-CWP-004, BR-CWP-039, BR-CWP-013, BR-CWP-010]
stories: [US-CWP-029, US-CWP-030]
# Wiring: every story above cites `J44` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J44.spec.ts`. Release 4.
# ⚠ BLOCKED ON OQ-1396 — how long may a delegate hold access, and who may revoke
# it? The COLUMN (`expires_on`) and the permission set are built either way;
# the POLICY is stubbed `NotImplementedError("OQ-1396")` (step 8).
# ⚠ THIS JOURNEY FIXES AN AUDIT PROBLEM THE PRODUCT WOULD OTHERWISE INHERIT:
# without named delegates every portal action by a family member or a
# bookkeeper is recorded as the account holder, and the audit trail is quietly
# wrong on exactly the accounts where a dispute is most likely. Hard rule 7
# needs a NAMED actor, and this is where the name comes from.
# ⚠ FIXTURE NOTE: the flow document says "after the bookkeeper PAYS a bill an
# audit entry naming Kestrel Bookkeeping" — but Kestrel's permission set is
# See · Download (no Pay), and paying is release 5. The named-actor proof in
# release 4 is therefore on a DOWNLOAD and a REQUEST NOTE (step 6); the Pay case
# is asserted as the release-5 boundary through J. Alvarez, who holds See · Pay
# (step 7). Filed as DEF-CWP-3607; the flow document and
# US-CWP-029 TC-2 corrected 2026-09-03.
---

**Intent.** The screen that replaces a shared password, which is what customers do today
in its absence. An account holder gives somebody access **without giving them the password**:
a permission set drawn from `see · download · pay · save_method` — **never** `close_account`,
`change_owner` or `move_out` — an end date, and **their own audit actor**. The invitation
states **both directions** before the commit: what they would be able to do **and what they
would not**. Accepting adds **one entry to the invitee's set and nothing more**. And when
the delegate acts, the audit entry names **the delegate**.

**Upstream leaves (handoff in).** J37's session for **Maria Alvarez** (holder of four
accounts). `portal_delegate` rows: **J. Alvarez** `j.alvarez@example.com`, all four, *See ·
Pay*, ends 31 Dec 2026, `ACTIVE`. No row yet for Kestrel. Tenant `oak-ridge`. Bill
`BL-2608-0141`'s issued PDF on `1408 Elm St · Common areas`' sibling — the common-areas
account's own August bill. Clock **2 Sep 2026**.

**This journey leaves (handoff out).** ONE `portal_delegate` row: `granted_by_credential_id`
= Maria's, `invitee_email = accounts@kestrel.example`, `invitee_display_name = "Kestrel
Bookkeeping"`, `account_id` = the common-areas master, `permissions = [see, download]`,
`expires_on = 2027-06-30`, `status` walked `invited → active → ended`, and its
**`audit_actor_id`** — the point of the table. ONE `portal_credential` for the bookkeeper
(their own, a portal credential, never a staff role) whose `account_set` has **one entry**.
`audit_log` rows with `portal_actor_label = "Kestrel Bookkeeping"`. An **ended** row that
**stays** on the record.

**Fixture.** Screens `CWP-026` (*People with access*) → `CWP-021` (*Accept an invitation*)
→ any read or request by the delegate (`CWP-029`, `CWP-051`) → the audit viewer (staff).
Single-use token for the invitation. A revoked invitation and an expired one for the
negatives.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (row · set · audit actor · isolation) | Rule |
|---|---|---|---|---|
| 1 | Maria — `CWP-026` *People with access. Anyone you add can see and pay. Nobody can close the account but you.* | `DataTable` Person / Accounts / Can / Access ends / Status: **Maria Alvarez · You · All four · Everything · — · HOLDER** · **J. Alvarez · j.alvarez@example.com · All four · See · Pay · 31 Dec 2026 · ACTIVE** (✎ −). `InfoBar`: *Every action taken by someone you invited is recorded under **their** name, not yours.* Action *+ Invite someone* | Four fixed portal roles — account holder, invited helper, landlord or manager, not signed in — **not a permission builder**, and **not editable by a tenant**. The holder row has **no expiry** | BR-CWP-017 |
| 2 | *+ Invite someone*: `accounts@kestrel.example`, display name *Kestrel Bookkeeping*, account **Common areas** only, permissions **See · Download**, ends **30 Jun 2027** | ONE `portal_delegate` row; the table gains ***Kestrel Bookkeeping · accounts@kestrel.example · Common areas · See · Download · 30 Jun 2027 · INVITED***. The invitation goes through the outbound queue with a **single-use, unguessable token** | **negative:** the permission set **cannot contain `close_account`, `change_owner` or `move_out` at all** — assert the enum. The account named must be **in the granter's own set** — an invite naming an account outside it is refused. A **non-holder** (J. Alvarez) trying to invite is refused; an invitee trying to invite is refused | BR-CWP-009 · `US-CWP-029` TC-3/4/5/8 |
| 3 | The bookkeeper opens the link → `CWP-021` *M. Alvarez has asked you to help with an account* | `KVList` Account `1408 Elm St · Common areas` / **You would be able to** *See bills · Download receipts* / **You would not be able to** *Pay · Close the account · Change the owner · Move out* / Access ends *30 Jun 2027*. *Accept ✓* · *Decline* | **Both lists render from one field** — the negative list is the **complement** of `permissions`, not separate copy. The invitee may not be signed in and may not be a customer at all — the token read and the accept sit **outside** the account set, which is why they are their own two endpoints | BR-CWP-039 · `US-CWP-030` TC-1 |
| 4 | *Accept ✓* — having no login, the bookkeeper enrols (J35's shape, their **own** contact) | A **portal** credential for the bookkeeper — **never a staff role** — whose `account_set` is **one entry**: the common-areas master with `[see, download]`. **In nobody else's set.** The delegate row → `ACTIVE`; the token is **dead** on second use | **negative:** *Decline* → the row moves to `ended`, no entry added. Accept **twice** → the second refused. An invitation the holder **revoked** before acceptance → refused with a plain sentence. An invitation **past its end date** → refused | BR-CWP-004 · BR-CWP-009 · `US-CWP-030` TC-2…6/8 |
| 5 | **negative · the set is flat and the master confers nothing** — the bookkeeper requests `1408 Elm St · A` or `22 Palm Ct` by id | **Refused**, without revealing whether they exist. The bookkeeper's switcher renders as a **label** — one account | The master is one more entry, not a parent; a grant on it confers nothing over anybody else's account | BR-CWP-013 · BR-CWP-010 |
| 6 | The bookkeeper **downloads** the common-areas August bill (`CWP-029`) and **adds a note** to an open request (`CWP-051`) | Both allowed under *See · Download*. **The `audit_log` rows carry `portal_actor_id` = the delegate's actor and `portal_actor_label = "Kestrel Bookkeeping"` — not Maria Alvarez.** Assert the label on the row, not the holder's name | This is what the table is for: without it every portal action by a bookkeeper is recorded as the account holder. `submitted_by_credential_id` on any reading the delegate sends (J39) is **theirs** | hard rule 7 · `US-CWP-029` TC-2 |
| 7 | **release 5 · boundary** — J. Alvarez (See · **Pay**) pays a bill on `1408 Elm St · A` | The Pay control is **held** today. When rails land: ONE payment row with `portal_credential_id` = J. Alvarez's, and **the audit entry names the delegate** (`US-CWP-045` TC-10). A delegate may manage **their own** stored method only, never the holder's, and step-up needs a **fresh** code (`US-CWP-022` TC-5/7) | Kestrel (See · Download) attempting to pay is **refused** — assert on `portal_delegate.permissions` | BR-CWP-040 · hard rule 7 |
| 8 | **boundary · `OQ-1396`** — the retention / revocation **policy** | `NotImplementedError("OQ-1396")` — the id in the code. Whether twenty-two months is allowed, whether anybody is prompted to review it, and whether the **utility** may revoke as well as the holder are the PO's (a maximum term · an annual review prompt · manual removal only) | **The column and the permission set are built either way; only the policy is stubbed.** Nothing here invents a maximum term | `OQ-1396` |
| 9 | **negative · expiry and removal** — a twin delegate whose `expires_on` was yesterday makes a request; Maria presses **−** on Kestrel | The expired delegate is refused **on their very next request** — not on their next nightly anything. Removal moves Kestrel's row to **`ended` and it stays on the record** — a revocation history that cannot answer *who could see this last year* is the defect | An ended row's credential keeps its own set minus the entry; nothing is deleted | `US-CWP-029` TC-6/7 · hard rule 4's shape |
| 10 | **tenant isolation** | A Pine Hill invitation token opened under `/oak-ridge` → refused. An invite naming an Oak Ridge account → refused. The bookkeeper's credential does not authenticate on `/oak-ridge` | RLS `FORCE` on `portal_delegate`; `app.tenant_id` from the path | hard rule 1 · `US-CWP-030` TC-7 |
| 11 | **INVARIANCE** | The permission set never held a closing, ownership or move-out right; both directions were stated before every accept; each delegate's set had exactly the entries granted and no more; every delegate action was audited under **their** name; the ended row remained; the master conferred nothing | The holder's own actions stayed audited as **Maria Alvarez** — the two actors never blurred | BR-CWP-009 · BR-CWP-017 · hard rule 7 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The retention policy — maximum term, review prompt, utility-side revocation | `OQ-1396` |
| b | A delegate **paying** and being named on the money audit row | Rails — release 5. The download and the note carry the named-actor proof now |
