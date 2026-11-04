# Walk — a customer sends their own meter reading (gap E, 2026-10-17)

`DEF-CWP-10175` · `US-CWP-042` · screen `CWP-035` at `/:tenant/portal/usage/submit`.
Script: `10-scripts/def_cwp_10175_self_read_walkthrough.mjs`. Result: **10 of 10 checks PASS**.

## World

- A private copy of the local database (`createdb -T smartbillhub smartbillhub_rdcwp`),
  this branch's backend on 8025 and its compose build on 8105. Copy dropped and both
  servers stopped afterwards; 8000/8080 untouched.
- Tenant `brazosbend`; staff `dana@brazosbendutilities.com`; customer
  `alvarez0@example.invalid` on account `AC-2026-00001` (101 Silver Creek Rd · Unit 1),
  two meters: water `W-5000` (kgal, last read `1,024` on 10/11) and electric `E-5000`
  (kWh, last read `3,400` on 10/11).
- **One setup change, stated:** on the copy only, the read-interval check's lower bounds
  were set to 1 day (they are 20/25). With the real bounds, any reading sent within 20
  days of the last one is flagged *Read interval* — correctly, it is the same check a
  clerk's reading meets (`BR-CWP-067`) — and there would be no "normal" reading to show.

## What was clicked and what came back

| # | Step | Seen |
|---|---|---|
| 01 | Staff → Settings → Customer portal: portal live, **Self-read ON** | switch `aria-checked=true` |
| 02 | Customer → Readings | **Send a reading** in the head, links to `/brazosbend/portal/usage/submit` |
| 03 | Send us your reading | Which meter (*Water · W-5000*), date opens on today, dial box, held photo; rail LAST READING *Taken 10/11/2026 · 1,024* and *Expected now · about 1,028* |
| 04 | `1027` on W-5000, sent with **Enter from the dial box** (keyboard only) | **RECEIVED** — *1,027 on 10/17/2026*, announced (`role="status"`) |
| 05 | Staff → Reads, `W-5000` | new row 10/17, Source **Self-read · Customer**, status OK; DB: `source=customer`, `read_method=self_read`, `3 kgal`, `status=ok` |
| 06 | `23400` on E-5000 | **RECEIVED – WE WILL CHECK IT** — *That is about 25 times your usual.* |
| 07 | Staff → Reads, `E-5000` | row 10/17, Source **Self-read · Customer**, status **High usage**; DB: `20,000 kWh`, `status=high`, `disposition=accept_with_flag` |
| 08 | Staff → Self-read **OFF** | switch off |
| 09 | Customer → Readings | **no** Send a reading (absent, not greyed) |
| 10 | Customer → `/usage/submit` typed in | no form — *Readings are not taken online here.* and *See your readings* |
| 11 | 390px | no sideways scroll; meter, date and dial boxes 44 / 44 / 56px tall |

Two `audit_log` rows `portal.meter_reading.submitted`, `actor_user_id` NULL, the payload
naming the portal customer and session, `source=customer`, `flagged` false / true.

## The eight accessibility questions (CWP-035)

1. Keyboard only — yes: every control is a native select/input/button/link; step 04 sent with Enter.
2. Focus visible — the kit's focus ring on every control (screenshots are not focused).
3. Labels attached — every box is a `<label for>`; a refused box gets `aria-invalid` and
   `aria-describedby` to its error line (asserted in `SendReading.dom.test.tsx`).
4. One main heading — *Send us your reading* is the only `h1`.
5. Contrast — kit tokens only; no new colours.
6. Narrow and enlarged — 390px reflows to one column, targets ≥ 44px; 320px not walked.
7. Announced — *Received* is a `role="status"` region; field errors sit in a polite live region.
8. Before money moves — no money moves; the result states what was received and whether it will be checked.
