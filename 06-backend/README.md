# 06-backend — Django service (W0 scaffold)

Stack: Django 5 + DRF (+drf-spectacular, TD-19) · PostgreSQL 16 · Celery/Redis (TD-17). Python 3.12.

## Structure = the law (B8)

```
config/            settings (base/local/test/production), celery, urls
core/              cross-module kernels: money · units · tenancy(RLS ctx) · rls ·
                   idempotency · audit · permissions · pagination
apps/<module>/     ONE app per doc module (13): api.py → services.py → selectors → models.py
db/                SQL applied by migrations (extensions; RLS policies are HUMAN-OWNED)
tests/             cross-module suites: golden/ (B5 contract, xfail→must-pass) ·
                   tenant isolation · immutability
```

## The laws that bind this app
- **LAW 0 (B8):** boring explicit code; a junior developer follows any service cold; simplicity beats DRY.
- **Layering (B8):** `api.py` is thin (parse → service → serialize); `services.py` is the ONLY write path; selectors read; no cross-module model imports — cross-module data flows through the owning module's service or the reviewed FK set (B2 §2).
- **🔒 HUMAN-OWNED** (CLAUDE.md): RLS policies · rating engine · ledger posting · idempotency keys · money rounding · migration ordering. Files carry `HUMAN-OWNED` docstrings and stay `NotImplementedError` stubs until a human writes them (gate G7).
- **Money:** `Decimal` only — `core.money`; float in a money path fails CI by grep (G6).
- **Every story file** carries the Trace header + machine-stamped Lifecycle trailer (B12; gates G1/G2/G11).

Run gates locally: `python3 ../10-scripts/gates/run_gates.py`. Docs: `04-docs/` — start at CLAUDE.md.
