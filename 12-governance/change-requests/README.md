# Change requests — one file each

**PO ruling 2026-09-03**, verbatim:

> *"one file per CR from here. `12-governance/change-requests/CR-068-customer-portal.md`, with
> `11-change-requests.md` kept as the index — the CR number, its title, its status, and a link."*

## The rule

**Every change request from `CR-069` onward is written here, in its own file.** The slug is two or
three words, lower case, hyphenated — enough to recognise the CR in a directory listing without
opening it.

⚠ **THE NAME CHANGED ON 2026-09-10 BY PO RULING: FROM `CR-090` ONWARD IT IS
`CR-###-<BRCnn>-<short-slug>.md`** — the running number, then the code of the branch that raised it,
then the slug. `CR-090-BRC01-some-change.md`. PO verbatim: *"we are going to now work on 2 or 3
branches symeteniouly - so we dont want two branches write same CR number and when we merge we land
into problem"* and *"Ensure you assing branch Suffix to CR number"*.

⚠ **`CR-068`–`CR-089` KEEP THE NAMES THEY ALREADY HAVE** — `CR-###-<short-slug>.md`, unchanged.
Nothing is renumbered and nothing is respelled; every citation of them still resolves.

⚠ **The suffix is PROVENANCE, not the thing that makes the number unique.** Two branches can both
reach for ninety, write `CR-090-BRC01` and `CR-090-BRC02` in two *different* files, and merge
cleanly with nothing going red — the string differs, the number does not, and a number is what a
person says out loud and cites from a business rule. Uniqueness comes from a **disjoint number block
per branch**, opened in [`../14-id-reservations.md`](../14-id-reservations.md) before that branch
starts, and from `G17` failing a duplicate NUMBER even when the suffixes differ. **The whole rule,
its reasoning and its three layers are [`../13-change-process.md`](../13-change-process.md) step 0 —
read it before allocating a number.**

**`../11-change-requests.md` keeps the index**: one row per CR — the number, the title, and where its
text lives. A new CR adds a row there in the same commit that creates its file here. **A file here
with no index row is invisible; an index row with no file is a broken promise.** Neither is
acceptable and both are cheap to avoid.

## Why this exists, measured rather than asserted

`11-change-requests.md` reached **2.5 MB and 30,491 lines across 80 change requests** before the
ruling. Three things follow from a file that size, and all three had already happened:

* **GitHub refuses to render it in a browser.** A register nobody can open is not a register.
* **Every lane touching any CR contends for one file.** That is precisely the shared-file hazard
  hard-won law 11 exists for, and the register-deletion guard fired on this file three times on
  2026-09-03 alone.
* **One CR can be 815 lines.** `CR-068` is, and the next two are expected to be larger.

## What did NOT move, and why that matters

**`CR-001`–`CR-067` stay in `11-change-requests.md`, untouched.** Every citation in every register,
docstring, test and commit message that names one of them still resolves. **Moving them would be a
mass rewrite of a shared file to no one's benefit** — the thing law 11 is written to prevent — and it
would buy nothing, because those CRs are closed history rather than working documents.

✅ **RATIFIED BY THE PO, 2026-09-03.** Leaving the sixty-seven was the integrator's judgment, not part of the ruling, so it was put to the PO in those words — *"Only CR-068 moved. CR-001 to CR-067 stay exactly where they are"* — and the reply was ***"yes I agree"***. **Do not re-open it.** A future session proposing to tidy `CR-001`–`CR-067` into per-file form is re-asking a settled question, which hard-won law 13 exists to stop.

**`CR-068` moved** because the PO's ruling names it by path, and because it is the CR being built
from right now. The move was verified by comparing both copies byte-for-byte **before a single line
was deleted** from the original.

## Writing one

Follow `../13-change-process.md`. All nine steps, in order, and the number is allocated **the moment
a change arrives** — not when work starts. The file is created at step 0, holding nothing but the
requester's words verbatim and the date; everything else is added as the steps are worked.

**Nothing about the process changed.** Only where the text lands.
