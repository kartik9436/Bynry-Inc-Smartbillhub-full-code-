# High consumption alert — E1 walk (CR-182-BRC10, PO A1–A5 2026-10-14)

Walked 2026-10-14 by lane HIGHUSE on a **private copy** of the dev database
(`smartbillhub_highuse`, made with `createdb -T smartbillhub`, migrated with this
branch, dropped afterwards), Brazos Bend Utilities, backend on 8006 and the built
front end on 8086, signed in to the portal as Ana Alvarez
(`alvarez0@example.invalid`, AC-2026-00001) at 1440 px, through
`10-scripts/cr182_high_consumption_walk.mjs`. **Every check printed PASS.**

**Set-up, measured before:** Ana's water meter W-5000 used **8 kgal** a month
(08/31, 09/30, 10/11). The utility's water rule: high above **200%** of the
trailing average **and** more than **1 kgal** over it (BR-MET-020/120).

## 1 · A 10× reading is entered

Her 10/11/2026 water reading was re-keyed from **1,024** to **1,096** on the dial
— **80 kgal** used — through `metering.services.supersede_read` (the door the
staff Reads correction form posts to), as Dana. The staff rule flagged it
(`ratio_pct 1000`, `delta_over_average 72 kgal` > floor 1 kgal). **At that moment,
before any bill:**

| Shot | What Ana sees |
|---|---|
| `1-home-high-consumption-alert.png` | Home › *Needs your attention*: **HIGH CONSUMPTION ALERT** · *Water reading on Oct 11, 2026: unusually high.* · **See your readings** → `/brazosbend/portal/readings` |
| `2-readings-tag.png` | Usage › Readings: the 10/11/2026 row (80 kgal) carries **High consumption alert**; no other row does |

## 2 · Billed

An October bill run for her cycle (10/01–10/12, bill date 10/13) through the
real bill-run views in-process as Dana — create, check, work out, release with
all five confirmations, issue. The high-usage case was settled by the utility's
own default (*Bill as is*) exactly as before this change. **BL-2610-000251,
$780.10**, water $649.30 (65 kgal in tier 3 at $8.48).

| Shot | What Ana sees |
|---|---|
| `4-home-last-bill-higher.png` | Home: **HIGH USAGE** · *Your last bill is higher than usual.* · **See why →** → `/brazosbend/portal/bills/BL-2610-000251/comparison`; the reading alert has gone (the reading is billed) |
| `5-bill-high-usage.png` | The bill: **HIGH USAGE** beside *Why is this different? →*, top right; nothing longer |
| `6-bill-comparison.png` | *See why* lands on the bill's comparison |
| `7-readings-tag-after-billing.png` | The tag stays on the reading after billing |

## Records checked (read from the database after the walk)

| Check | Result |
|---|---|
| `meter_reads` W-5000 10/11 | old head 1,024 / 8 kgal, high `ok`, **superseded**; new head 1,096 / **80 kgal**, status `high`, high `warning`, lifecycle `billed` |
| `outbound_messages` `usage_alert` | **exactly 1** row: source = the new reading, `email`, `queued`, to `alvarez0@example.invalid`, `email_high_usage_alert` **v1**, event `high_usage_alert`, not held — still 1 after the bill run |
| The email, rendered from its pin | Subject *High consumption alert on account AC-2026-00001* · *Hi Ana, Your Water reading on 10/11/2026 was much higher than usual. Used 80 kgal. It may be a leak, or the reading may be wrong. You can see your readings in your online account. If you think the reading is wrong, call +1 (281) 555-0164. Brazos Bend Utilities* — no blank field |
| `audit_log` | `outbound_message.queued` for the row; `notification_rule.updated` for the SET-12 rule, `source: notifications 0022 · CR-182-BRC10` |
| SET-12 *High usage alert* | `notifications/0022` printed *switched on for 1 utility(ies); 0 set by the utility left alone* → enabled, email ON with `email_high_usage_alert`, no SMS row |
| The bill | BL-2610-000251 issued, `bill_payload.services` water `read_id` = the flagged reading |

**Operator step on an existing tenant:** the email's wording is a newly seeded
class, so it was planted with `seed_notice_templates` (the half of
`manage.py seed_demo --tenant brazosbend` that seeds notice templates) before
the reading was entered — *created: ['email_high_usage_alert']*. Without it the
row is still queued and HOLDS at dispatch with the missing-template reason.

**Noticed, not changed here:** the Home sentence formats the date in the
browser locale (*Oct 11, 2026*) as the other Home sentences do (`onDate`), not in
the utility's MM/DD/YYYY the tables use.
