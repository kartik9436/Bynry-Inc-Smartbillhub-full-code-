# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-015 (EP-RBS-01) — CR-075 wave B task B3: the executor.
# Rules:    BR-RBS-003 · BR-RBS-007 · BR-RBS-009 · BR-RBS-012 · BR-RBS-020 ·
#           BR-RBS-023 · CLAUDE.md hard-won law 14
# Tests:    06-backend/tests/test_us_rbs_015_conformance.py ·
#           06-backend/tests/test_rbs_savepoint_pg.py (TC-RBS-5, PostgreSQL)
# Impacts:  apps/runbooks/services.py (open_run / close_run)
# ───────────────────────────────────────────────────────
"""The engine — pin the scope, evaluate, close, and freeze the report.

`executor.py` holds all of it. The package exists so that the two acts the
ENGINE performs and no runbook may — raising work items and writing audit rows
— have somewhere to live that is visibly not a port (`12-the-contract.md` §2).
The work-item upsert lands here in wave C.
"""
