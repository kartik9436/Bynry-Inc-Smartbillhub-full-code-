# Module — rating (product name: **Plans & Rates**)

PURE module: reads + tariff version in, priced lines out. No side effects — unit-tested against B5 golden tests. Engine is HUMAN-OWNED (B4).

**Owns (B2):** tariffs, tariff_versions, rate_tiers, time_of_use_windows, charges, taxes
**Screens:** S9–S13 Plans & Rates
**Boundary rule (B1):** no other module writes this module's tables; cross-module reads via service functions only.

**Update 2026-08-12 (PO ruling batch).** Three landings in `02-business-rules.md`: **BR-RAT-004** gains *"Split by days"* — a tariff change inside a back-billed period prices as two day-weighted segments, worked group **35.56** (not the 35.55 the question illustrated, because BR-RAT-003 rounds per line), and a segment with no read on the cut day gets a day-weighted usage estimate **marked as estimated** by default (OQ-155 · OQ-191); **BR-RAT-063** is new — a mid-cycle plan-change preview shows the **base half only** and states that usage is excluded (GT-3: 15/30 × 30.50 = **15.25**); and **BR-RAT-030 / BR-RAT-035** record that their delete/audit-lock guards became LIVE on 2026-08-12, when billing published the counters they had been asking an unwired seam for since W1 (DEF-079).
