# Edit a plan — photographed beside images 37–44 (CR-167-BRC10 round 3 task 8, lane PLAN-EDIT)

Chromium at 1440, PostgreSQL 16 (`sbh_planedit`), Brazos Bend, signed in as Dana. Walk:
`10-scripts/cr167_plan_edit_walk.mjs`; what it printed: `walk-output.txt`; database before and after:
`db-before.txt`, `db-after.txt` (`10-scripts/cr167_plan_edit_db_check.sh`); the Audit read:
`audit-csv.txt`. Every photograph below was opened and is not blank.

**Figures differ from the images by design (B14 rule 37).** The plan walked is `SCW-IND` (*Sample —
Industrial*): it sells electric and water, not water, sewer and trash; the drawing's *$19.00*, *5
units* and *09/01/2026* read *—* (its water base does not resolve, so no part-sum is shown —
`DEF-RAT-9351`'s rule), *1 unit* and *08/01/2026* here because those are the plan's real figures.
An earlier run on `SCW-COM` (same results) found judgment 4 of CR §14.2 and was re-shot after the
fix.

| Image | Photograph | Same | Different, and why |
|---|---|---|---|
| 37 · section Edit opens a step | `37-detail-section-edit.png` | `?change=change&step=2` opens *Change from a date* on **Charges**, Services ticked, *This plan* on the right; the plan's charge rows with version and from-date; *+ Add charge code*, *Not listed? Define it ↗*, Taxes with *Combined*; Back · Continue | the plan's own rows (one late-fee code, two taxes) |
| 38 · Name and details · Details | `38-edit-info-1.png` | *What to change* with three cards, *Name and details* chosen (accent top rule); rail *Details · Review*; *Plan* with the name box and **Code as a fact**; *Customer classes* dropdown; *Description for customers*; *Intended for* with the three ticks and the notes table; *Services, charges and billing* locked, *🔒 Change from a date.*, a three-cell strip; Cancel · Continue | the notes table is empty (*None*) because this plan has no note; the strip's figures are this plan's |
| 39 · Name and details · Review | `39-edit-info-review-unchanged.png`, `39-edit-info-review.png`, `39b-edit-info-saved.png` | *What changes* (*Nothing changed yet.* as a blue note when nothing moved; a before → after table once the description moved); *Plan* with **Edit**; every priced section WITHOUT Edit; Billing terms; *Dates* as facts (*Starts* · *Ends* *No end*); Back · **Save changes** | the drawing's *What changes* has no example row; ours shows the moved field |
| 40 · Change from a date · first step | `40-edit-change-1.png` | rail *Services · Charges · Billing · Review*; the services table array with schedule, base (code, version, from-date), minimum and surcharge tick per row; *Monthly base charges*; *Switch more services on ↗*; *Outside city limits*; Cancel · Continue | this plan surcharges nothing (*No, same price*) |
| 41 · Change from a date · Review | `41-edit-change-review.png` | *What changes* (Minimum bill None → 12.00); Plan without Edit; every priced section with **Edit**; *Dates* with *New version starts* * and *Ends*, *Today's version ends 12/31/2026.*, *Leave empty if it has no end.*; *Reason* *, *Shown in Audit.*; *How it is saved* — *v1 · today 08/01/2026 – 12/31/2026 Gets an end date*, *v2 · new 01/01/2027 – No end New version*; the blue *1 unit moves to v2 on 01/01/2027.*; **Back · Save new version · Publish new version** | — |
| 42 · Change from a date · *published* | `42-edit-change-refused.png`, `42-edit-change-published.png` | the image draws the REFUSED state: *Enter the reason.* under a pink box and *Fix 1 thing first.* beside the buttons — ours the same (no failure card, `DEF-RAT-9362`); the published state: tick, *Sample — Industrial saved*, *v2 starts 01/01/2027. Logged in Audit.*, *Back to plan* | our refused box is outlined, not pink-filled (kit, rule 44 — the New form's §11.1 difference) |
| 43 · Fix a mistake · first step | `43-edit-correct-1.png` | *Fix a mistake* chosen; the same four steps and the same Services step | — |
| 44 · Fix a mistake · Review | `44-edit-correct-review-noreason.png`, `44-edit-correct-review.png`, `44b-edit-correct-saved.png` | *What changes* (Budget billing Not offered → Offered); priced sections with Edit; *Dates* as facts (*08/01/2026* · *12/31/2026*) and *Reason* *; *How it is saved* — *v1 · today … Superseded, kept*, then the correction row, *Replaces v1*; the amber *Issued bills keep v1. Correct those bills separately.*; Back · **Save correction** | the drawing labels the new row *v2 · correction*; the server keeps the corrected version's number, so ours reads **v1 · correction** (rule 37; §14.2 judgment 6). The end date reads 12/31/2026 because v2 had already been filed from 01/01/2027 |
| Audit (ruling 13) | `audit-after-three-ways.png`, `audit-csv.txt` | the three ways are each a row: *edited* (description before → after), *new_version* and *published* (*Starts: 01/01/2027*, the reason), *correction* (the reason) | the correction row does not say WHAT moved (budget billing) — `DEF-RAT-9363`, filed, the server's |
