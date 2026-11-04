"""customers 0061 — **a ladder stopped by hand can say what happened.**

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-09-20 under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). Ledger row: `12-governance/09-human-review-ledger.md`.

`CR-125-BRC07`, the disconnect wizard rebuilt to its drawing. Blueprint p137
(`05-prototype/02 Accounts Menu Blueprint.pdf`, rendered as an image per B14
rule 42) draws step 2's *"Or stop the ladder without a protection"* as three
radio reasons AND a free-text line under them labelled **`What happened`**,
holding *"Customer disputes INV-26-0411 on a meter reading"* and captioned
*"Recorded with the act and with who did it."*

WHAT WAS WRONG
--------------
There was **no parameter and no column**. `disconnects.stop_by_hand` took
`reason` — one of three CODES (`clerk_error`, `dispute`,
`regulator_instruction`) — and nothing else, so the sentence that makes a
stopped ladder readable a year later had nowhere to go. A utility that has
stopped chasing a real debt and cannot say why cannot answer an auditor.

WHY A COLUMN AND NOT THE TWO CHEAPER ANSWERS
--------------------------------------------
The whole decision, with both refused options, is on
`disconnects.DisconnectCase.stopped_note`. In short:

* **`audit_log` alone** was refused because `audit_log` is PRUNED on a
  retention schedule (CLAUDE.md hard rule 4's own note; whether an audit row may
  be exempt is `OQ-1340`, OPEN). A record that ages out is not the record a
  regulator asks for.
* **Reusing `stopped_reason`** was refused because that column holds a CODE from
  a closed set of three, and `stop_by_hand` refuses anything outside it BY NAME
  so that *"a fourth way to stop chasing a real debt needs a ruling"*. Letting
  prose into it would delete that guard in the act of reusing the column.

⚠ **THIS WAS OURS TO DECIDE AND IT IS WRITTEN DOWN** (CLAUDE.md hard-won law
13): it collides with no signed rule, moves no ❄️ FROZEN B4/B5 figure and is not
a fact only the PO holds. A question here would have been the failure to make a
decision. Decision log 2026-09-20.

WHAT THIS DOES
--------------
**ONE nullable TEXT column on `disconnect_cases`. Nothing else.** No index
(nothing sorts, pages or filters on prose), no default, no check, no backfill
and no data migration of any kind.

⚠ **NULLABLE, AND NOT MADE REQUIRED — THAT IS THE DESIGN AND NOT A SHORTCUT.**
Every case stopped before today has no note and a backfill would be fiction
(hard rule 4: no migration may write one). Requiring a note would REFUSE a
stop, and on this ladder a refused stop means a disconnection continues because
a clerk had nothing to type. The note is evidence; it is never a gate.

⚠ **NO CHECK CONSTRAINT, DELIBERATELY.** `0058`'s `ck_accounts_close_reason`
exists because that column holds one of five CODES. This one holds a sentence a
human wrote, and a check over free text is a check that can only be wrong.

REVERSIBLE, AND WHAT REVERSING COSTS
------------------------------------
`AddField` reverses to `RemoveField` cleanly. **Reversing DROPS every recorded
note**, which is data loss rather than a schema change — so take a dump of
`disconnect_cases (id, stopped_note)` first. It is free on day one, when no row
has a value.

ORDERING — AND THE HAZARD THIS FILE WAS WRITTEN AGAINST, WHICH THEN HAPPENED
---------------------------------------------------------------------------
Depends on `0060_br_cus_1030_seller_link_ended`, the leaf on
`origin/claude/kind-wozniak-rl0uzt`.

⚠ **IT WAS WRITTEN DEPENDING ON `0059` AND RE-POINTED WITHIN THE HOUR, AND THE
SEQUENCE IS WORTH KEEPING.** When this file was authored, `0060_*` existed on
**no remote ref at all** (checked across all 70) — a sibling lane held it
unpushed, and this lane is forbidden to touch that file, so there was nothing to
depend on. It was therefore written against `0059` **with this paragraph already
in it**, naming the exact failure that would follow and the one-line fix.
`0060` landed forty minutes later, also depending on `0059`, and for that window
the branch really did carry **two leaf nodes**.

⚠ **TWO LEAVES IS NOT A TEST FAILURE — IT IS EVERY TEST IN THE PROCESS.** Django
refuses with *"Conflicting migrations detected; multiple leaf nodes in the
migration graph"*, which names neither lane and reads exactly like a broken
checkout. `DEF-2872` is that failure, recorded in CLAUDE.md law 12, and the
reason this file states its ordering instead of assuming it.

**THIS WAS THE SIDE THAT MOVED, AND THAT WAS DELIBERATE RATHER THAN POLITE.**
This migration adds ONE column to `disconnect_cases`, a table `0060` does not
touch and whose column no other migration references, so re-pointing it can
reorder nothing. Moving `0060` instead would have meant editing another lane's
file; a merge migration would have meant a third file for a one-line problem.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # ⚠ Re-pointed from `0059` the moment `0060` landed — see ORDERING above.
        ("customers", "0060_br_cus_1030_seller_link_ended"),
    ]

    operations = [
        migrations.AddField(
            model_name="disconnectcase",
            name="stopped_note",
            field=models.TextField(blank=True, null=True),
        ),
    ]
