# The premises and units import templates, corrected — `DEF-MET-5802` · `DEF-MET-5803`

**2026-09-19.** The Product Owner read the generated import templates and asked
for the corrected files: *"okay I want updated CSV file"*. These are them.
`premises-sample.csv` and `units-sample.csv` beside this note are byte-for-byte
what the product now serves from **Imports → step 1 → Download sample**.

They are **evidence, not a source**. The file a utility downloads is generated
from `sample_columns()` in `06-backend/apps/metering/import_runs.py` every time
it is asked for, and nothing reads the two CSVs here.

⚠ **AND THE SAMPLE IS DIFFERENT FOR EVERY UTILITY, BY DESIGN.** The services
are your own enablement, the account type and the owner category are your own
Settings lists, and a units row names your own first premises. So these two
files are *"what this template looks like for one utility"* — our test fixture
— and not a fixed artefact. Your own download will differ in those cells and
should.

⚠ **THEY HAD ALREADY DRIFTED ONCE.** The committed premises file said `Sample
Owner` while the product was serving `Creekside Laundromat` on the beta tenant.
Neither was wrong about itself; nothing compared them. A test now regenerates
both for the fixture tenant and refuses any difference, so the next drift is a
red build rather than a surprise.

## What changed, in one line

The premises template went from **31 columns to 24** and units from **20 to
15**: fourteen columns were removed because nobody had ever chosen them, and
two were added — one so an owner can be contacted, one so an owner record can
actually be created.

## The premises header row (24)

```
Premise ID (existing only),Name,Address line 1,City,State,Postal code,Inside city limits,Premise type,Services available,Area / sub-area,Owner name,External reference,Lat,Lng,Status,GIS parcel ID,Owner is a person or a company,Owner Social Security number,Owner driving licence,Owner phone,Owner Tax ID,Owner account type,Owner category,Owner email
```

## The units header row (15)

```
Parent premise,Unit number (existing only),Unit label,External reference,Unit type,Floor,Floor area (sq ft),Lat,Lng,GIS point ID,Plan,Plan effective from,Plan locked,Vacant standby,Common area
```

## The fourteen columns that went, and why

These were never decided on. The two templates DERIVED their column list from
the database table, so **any field added to the premises table appeared on every
customer's template the next day**, wearing a heading generated from its field
name. That is how *"Gis parcel id was"* and *"Gis verified at"* became things a
utility was asked to fill in.

Every one of them is written by our own address-matching process. A utility
typing *"Gis verified at"* into a spreadsheet is asserting the result of a check
only the system is entitled to make.

| Premises (9) | Units (5) |
|---|---|
| `gis_unchecked` | `gis_point_id_was` |
| `gis_checked_by` | `gis_key_changed_at` |
| `gis_checked_at` | `gis_status` |
| `gis_parcel_id_was` | `gis_verified` |
| `gis_key_changed_at` | `gis_verified_at` |
| `gis_status` | |
| `gis_verified` | |
| `gis_verified_at` | |
| `owner_manager` — the legacy owner-name box, see below | |

**The two real GIS keys STAY**, and they are the point of the dividing line:
`GIS parcel ID` on premises and `GIS point ID` on units are what a **city gives
a utility**. They are in the file being migrated. Everything else in that block
is ours.

## The owner columns

**The template could already name an owner.** `DEF-MET-5803` was filed saying it
could not, and that was wrong — the `Owner` column is a real field, it is what
the owner rules read, and a row with it empty creates nobody at all.

What was real is that there were **two name-shaped columns and only one of them
created anybody**: `Owner` and `Owner name (legacy)`. A utility filling in the
more explicit-sounding of the two got an address and no owner account. The
legacy box is gone and the survivor is now labelled **`Owner name`**.

**`Owner email` is new.** An owner account is created active and it bills. With
six identity columns and no contact column, a utility could load 5,000 owners
who could be billed and not reached — no emailed bill, no portal invitation.
The Accounts template, which is the other way a customer gets created here,
has carried `Email` and `Phone` all along; the two doors should not disagree.

⚠ **An email is NOT an identifier.** An owner account is still created from a
driving licence, a Social Security number, a phone or a Tax ID, exactly as ruled
on 2026-09-01. A row with a name and an email and nothing else still creates
nobody, and a test asserts it.

**`Owner category` is new too, and it fixes a reported bug.** A user reported
that importing premises with owner details did not generate the Master Account.
The account WAS generated — what was missing is that **nobody owned it**.
Reproduced on a real database: a complete, correct row created the account and
then left the address with no owner record at all, the name surviving only in
the legacy free-text box. The import refuses to invent a category (a name is not
proof of a landlord) and was never given a way to be told one, so **every row of
a first migration took that path**, which is exactly when the feature is used
for the first time.

With a category stated, the owner record is created and linked, and the account
is joined to it. The five categories — Owner-occupier, Landlord, Property
manager, HOA, Builder — come from the editable list on Settings, so a utility
that renames or adds one gets its own words here.

⚠ **Leaving it blank is still allowed and still loads.** The address loads, the
owner account is still created, and the owner record waits for someone to type
it — which is what happens today. The import says so at the rehearsal step
instead of leaving it to be discovered later. A utility that has not set its
categories up yet must still be able to load its addresses.

## The example row, and why each cell is what it is

**The owner section is filled in, and that is a correction.** Until this file
was reviewed the sample said `person` in the owner-kind cell and left the other
eight owner columns empty — so the row demonstrated **exactly the problem that
started this work**: owner details apparently supplied, and no Master Account
generated. A sample is read as instruction, and one committing value beside
eight blanks teaches that the rest are decorative.

The row now earns an owner account and an owner record, and every cell in it is
either your own list or unmistakably fictional:

| Cell | What it is |
|---|---|
| `Owner name` | your own first owner where you have one, otherwise `Sample Owner` |
| `Owner is a person or a company` | `person` — the product's own word |
| `Owner phone` | `555-0142`, in the range reserved for fiction; enough on its own to create a person |
| `Owner account type`, `Owner category` | **your own** Settings lists, so the row validates on your utility and no other |
| `Owner email` | `example.test`, a domain reserved so it can never be a real mailbox |

**Still blank, and deliberately:** `Owner Social Security number`, `Owner
driving licence` and `Owner Tax ID`. There is no way to write a government
identifier that is not somebody's, so the sample does not try — the person in
it is created from the phone instead.

Also blank: a **GIS parcel key** and a **latitude**, which are your data and
ours to ask for rather than invent. Until today they read *"Sample gis parcel
id"* and *"Sample lat"*.

## How to regenerate

```
cd 06-backend
JOBS_EAGER=false .venv/bin/pytest tests/test_def_met_5802_declared_columns.py --reuse-db
```

That suite asserts the header rows above by name. To re-capture the files
themselves, call `import_runs.sample_csv("premises")` and `("units")` inside a
tenant context and write the second element of each answer.

## 2026-10-17 — both templates gain an optional **Created** column (`DEF-MET-10164`)

PO ruling of that date: the premises and units lists show **Created** and **Age**,
and *"Import (premises and units) may carry an optional Created column — the date
the property was first set up in the old system."* So both CSVs above now carry a
`Created` header with a blank sample cell (we hold no truthful old-system date to
put there).

| Created cell | What happens |
|---|---|
| blank | the record is dated the import day |
| your Settings date format (e.g. `03/14/1996`), or ISO `1996-03-14` | the record is dated that day |
| a date after today | that row is refused: *Date is in the future.* |
| any other spelling (e.g. `14/03/1996` on a MM/DD/YYYY utility) | that row is refused: *14/03/1996 is not MM/DD/YYYY.* |

**Correcting records already imported.** A file carrying only the premise (or
unit) number and `Created` — headed e.g. `Premise ID,Created` — loaded with
**Insert & update** changes the Created date of each record it names and nothing
else; each change is written to the audit log, old → new. Under **Insert new
only** those rows are refused as already on file.
