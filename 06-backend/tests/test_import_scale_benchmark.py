# ── Trace ──────────────────────────────────────────────
# Component: the CR-023 import runner at 60–80,000 rows — THE MEASUREMENT the
#            caps in `import_runs.py` are set from, and the one that says what
#            a worker's memory has to be.
# Defect:   DEF-MET-5756 — imports and exports cannot carry 60–80,000 rows.
# Change:   PO 2026-09-18 — designed for 3,000 accounts, assumption now
#           40,000–80,000. PO, verbatim: *"what if we test with option a first
#           instead increase worker ram to start with test whether is it okay
#           for 80k - if it does not work we can later go for option b"*.
# Rules:    BR-MET-038 (the upload caps) · BR-MET-096 (ONE runner) ·
#           CLAUDE.md hard rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""**HOW BIG DOES A WORKER HAVE TO BE TO IMPORT 80,000 ROWS?**

SKIPPED UNLESS `SCALE_ROWS` IS SET, and that is the same judgment
`10-scripts/cr026_import_benchmark.py` records for itself: these figures are the
INPUT TO A DESIGN DECISION — where the caps go, how much RAM the worker needs —
not an assertion about behaviour, and a twenty-minute case on every commit would
be paid for by every lane forever to re-learn a number that moves only when the
engine does. The assertions that hold the RESULT are in
`tests/test_import_scale_80k.py`, which is instant.

    cd 06-backend
    export DATABASE_URL=...                      # from ./.env
    SCALE_ROWS=80000 SCALE_TRACE=0 .venv/bin/pytest \
        tests/test_import_scale_benchmark.py \
        --ds=config.settings.pgtest --reuse-db -q -s -p no:randomly

⚠ **`SCALE_TRACE=0` MATTERS MORE THAN IT LOOKS, AND MEASURING WITH IT ON ONCE
COST THIS LANE A WRONG NUMBER IN A CODE COMMENT.** `tracemalloc` tracks every
allocation, so on a parse it inflated the SAME run from 27.2s to 117.0s and from
+224 MB to +398 MB — 4.3x the time and 1.8x the memory. With it on you are
measuring the tracer. Leave it off for anything anybody will quote; turn it on
only to find out WHICH objects a stage is holding.

⚠ **WHY `.django_db` AND NOT A ROLLED-BACK SCRIPT.** `cr026_import_benchmark.py`
owns the TIMING job and rolls its own transaction back; this one needed peak RSS
per stage, which that script does not sample, and pytest's fixtures give a real
provisioned tenant without re-implementing provisioning. The two answer
different questions and neither replaces the other.
"""
import csv
import io
import os
import threading
import time
import tracemalloc

import pytest
from django.db import connection

from apps.metering import import_runs

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_cr023_import_stages import MAPPING as PREM_MAPPING
from tests.test_cr030_w1_accounts_import import MAPPING as ACCT_MAPPING

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        not os.environ.get("SCALE_ROWS"),
        reason="benchmark — set SCALE_ROWS to run it (see this file's docstring)",
    ),
]


@pytest.fixture(autouse=True)
def _everything_inline(monkeypatch):
    """Run every stage IN PROCESS so it can be timed. A deferred stage does the
    identical work in a worker (`_transform_apply` / `_validate_apply` /
    `_load_apply` are the shared bodies), so this changes WHERE the work runs
    and not WHAT it costs."""
    monkeypatch.setattr(import_runs, "async_row_bar", lambda target, stage: 10**9)

ROWS = int(os.environ.get("SCALE_ROWS", "80000"))
TRACEMALLOC = os.environ.get("SCALE_TRACE", "1") == "1"
ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}

PREM_HEADERS = ["PREMISE_ID", "ADDR1", "CITY", "STATE", "ZIP", "PROP_TYPE",
                "UNIT_CNT", "SVC_AVAIL", "OWNER", "LEGACY_KEY", "INSIDE_CITY"]
STREETS = ["Bluestem Ln", "Cypress Creek Dr", "Willow Fork Rd", "Katy Hockley Cut Off",
           "Franz Rd", "Mason Rd", "Grand Pkwy", "Peek Rd", "Roesner Rd", "Westheimer Pkwy"]
CITIES = [("Katy", "TX", "77494"), ("Fulshear", "TX", "77441"), ("Brookshire", "TX", "77423"),
          ("Richmond", "TX", "77406"), ("Cypress", "TX", "77433")]
TYPES = ["single_family", "duplex", "apartment", "commercial", "mobile_home"]
OWNERS = ["Whitfield Rentals LLC", "Brazos Bend Holdings", "Katy Property Group LP",
          "Cinco Ranch Investments", "Harmon Family Trust"]
SVCS = ["electric", "electric,water", "water", "electric,water"]

ACCT_HEADERS = ["UNIT_REF", "ACCT", "NAME", "CUST_ID", "KIND", "SSN", "TYPE", "OPENED",
                "CURRENT", "31-60", "61-90", "90+", "DEPOSIT", "DEPOSIT_DATE"]
SURNAMES = ["Harmon", "Alvarez", "Whitfield", "Okafor", "Nguyen", "Delacroix", "Petrov", "Mbeki"]
GIVEN = ["Luis", "Rosa", "Dana", "Jerome", "Thi", "Camille", "Anatoly", "Nomsa"]


def _csv(headers, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row[h] for h in headers])
    return buf.getvalue()


def premises_csv(n, typed=True):
    def rows():
        for i in range(1, n + 1):
            city, state, zipc = CITIES[i % len(CITIES)]
            yield {
                "PREMISE_ID": "",
                "ADDR1": f"{1000 + i} {STREETS[i % len(STREETS)]}",
                "CITY": city, "STATE": state, "ZIP": zipc,
                "PROP_TYPE": TYPES[i % len(TYPES)] if typed else "",
                "UNIT_CNT": str(1 + i % 4),
                "SVC_AVAIL": SVCS[i % len(SVCS)],
                "OWNER": OWNERS[i % len(OWNERS)],
                "LEGACY_KEY": f"LEG-{880000 + i}",
                "INSIDE_CITY": "inside" if i % 3 else "outside",
            }
    return _csv(PREM_HEADERS, rows())


def accounts_csv(n, unit_refs=None):
    def rows():
        for i in range(1, n + 1):
            ref = unit_refs[(i - 1) % len(unit_refs)] if unit_refs else f"U-{100000 + i}"
            yield {
                "UNIT_REF": ref,
                "ACCT": f"A-{12000 + i}",
                "NAME": f"{SURNAMES[i % 8]}, {GIVEN[(i // 8) % 8]}",
                "CUST_ID": f"CUST-{100000 + i}",
                "KIND": "person",
                "SSN": f"{100 + i % 800:03d}-{10 + i % 80:02d}-{1000 + i % 9000:04d}",
                "TYPE": "residential" if i % 5 else "commercial",
                "OPENED": "2024-02-12",
                "CURRENT": f"{(i % 500) + 0.20:.2f}",
                "31-60": f"{(i % 90) + 0.10:.2f}",
                "61-90": "0.00",
                "90+": f"{(i % 30) + 0.00:.2f}",
                "DEPOSIT": "150.00",
                "DEPOSIT_DATE": "2024-02-12",
            }
    return _csv(ACCT_HEADERS, rows())


def _rss_mb():
    """Resident set size, MB — what the OOM killer actually sees."""
    with open("/proc/self/statm") as handle:
        return int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1048576


class Stage:
    """Wall clock, query count, peak RSS and peak Python allocation for one call.

    ⚠ **THE QUERY COUNT IS `execute_wrapper`, NOT `CaptureQueriesContext`.**
    `CaptureQueriesContext` forces `DEBUG=True`, STORES every SQL string, and
    Django then truncates its own log at 9,000 — so at 80,000 rows it both
    distorts the memory figure it sits beside and silently under-reports the
    count it exists to give. This counts and keeps nothing.

    ⚠ **RSS IS SAMPLED IN A THREAD.** `ru_maxrss` is a whole-process high-water
    mark that never falls, so it cannot attribute a peak to one stage.
    """

    def __init__(self, label, rows, trace=None):
        self.label, self.rows = label, rows
        self.trace = TRACEMALLOC if trace is None else trace

    def _sample(self):
        while not self._stop.is_set():
            self.peak_rss = max(self.peak_rss, _rss_mb())
            self._stop.wait(0.05)

    def __enter__(self):
        self.count = 0
        self.peak_rss = self.rss0 = _rss_mb()
        if self.trace:
            tracemalloc.start()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()

        def counter(execute, sql, params, many, context):
            self.count += 1
            return execute(sql, params, many, context)

        self._wrapper = connection.execute_wrapper(counter)
        self._wrapper.__enter__()
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.secs = time.perf_counter() - self.t0
        self._wrapper.__exit__(*exc)
        self._stop.set()
        self._thread.join()
        self.peak_rss = max(self.peak_rss, _rss_mb())
        self.peak = 0
        if self.trace:
            _cur, self.peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        print(
            f"  {self.label:<26} {self.secs:9.2f}s  "
            f"{self.secs * 1000 / max(self.rows, 1):8.3f} ms/row  "
            f"{self.count:>10,} q  "
            f"({self.count / max(self.rows, 1):5.2f} q/row)  "
            f"RSS {self.rss0:7.1f} -> peak {self.peak_rss:7.1f} MB "
            f"(+{self.peak_rss - self.rss0:6.1f})"
            + (f"  pyalloc peak {self.peak / 1048576:7.1f} MB" if self.trace else ""),
            flush=True,
        )
        return False


def _banner(text):
    print(f"\n{'=' * 100}\n{text}\n{'=' * 100}", flush=True)


# ── 1 · file widths for every target, from the repo's OWN shipped template ──
def test_measure__template_row_widths(brazos, dana):
    _banner(f"TEMPLATE ROW WIDTH PER TARGET (shipped sample_csv) -> bytes at {ROWS:,} rows")
    with tenant_ctx(brazos):
        for target in import_runs.TARGETS:
            _name, text = import_runs.sample_csv(target)
            lines = text.splitlines()
            body = lines[1:]
            width = sum(len(line.encode()) + 1 for line in body) / max(len(body), 1)
            print(
                f"  {target:<18} cols={lines[0].count(',') + 1:>3}  "
                f"mean row {width:6.1f} B  ->  {ROWS:,} rows = "
                f"{width * ROWS / 1048576:6.2f} MB"
                f"   {'OVER 10 MB CAP' if width * ROWS > 10 * 1048576 else ''}",
                flush=True,
            )
        print(f"\n  CSV_BYTE_CAP = {import_runs.CSV_BYTE_CAP:,} B "
              f"({import_runs.CSV_BYTE_CAP / 1048576:.0f} MB)   "
              f"CSV_ROW_CAP = {import_runs.CSV_ROW_CAP:,}")
        print(f"  the byte cap is reached at {import_runs.CSV_BYTE_CAP // 104:,} rows of a "
              f"104 B premises row and {import_runs.CSV_BYTE_CAP // 129:,} rows of a "
              f"129 B accounts row", flush=True)


# ── 2 · premises, end to end at ROWS ────────────────────────────────────────
def test_measure__premises_end_to_end(brazos, dana):
    _banner(f"PREMISES · {ROWS:,} rows · every stage on real PostgreSQL")
    text = premises_csv(ROWS)
    raw = text.encode()
    print(f"  file: {len(raw):,} B = {len(raw) / 1048576:.2f} MB "
          f"({len(raw) / ROWS:.1f} B/row)\n", flush=True)
    with tenant_ctx(brazos):
        with Stage("1 extract (parse+stage)", ROWS):
            run = import_runs.extract(dana, {
                "target": import_runs.TARGET_PREMISES, "source_kind": "file",
                "file_name": "premises.csv", "content": text, "session_ref": "scale",
            })
        run_id = run["id"]
        with Stage("2 transform", ROWS):
            import_runs.transform(dana, run_id,
                                  {"mapping": PREM_MAPPING, "row_handling": ALL_OFF})
        with Stage("3 validate", ROWS):
            import_runs.validate(dana, run_id)
        with Stage("3b dry_run", ROWS):
            dry = import_runs.dry_run(dana, run_id, "insert")
        print(f"     dry run: {dry.get('counts')}", flush=True)
        with Stage("4 load", ROWS):
            result = import_runs.load(dana, run_id, {"approved": True})
        print(f"     load: {result.get('counts') or result}", flush=True)


# ── 3 · accounts, stages 1-3 at ROWS (load is measured separately) ──────────
def test_measure__accounts_stages_1_to_3(brazos, dana):
    _banner(f"ACCOUNTS · {ROWS:,} rows · stages 1-3 (no units on file, so nothing loads)")
    text = accounts_csv(ROWS)
    raw = text.encode()
    print(f"  file: {len(raw):,} B = {len(raw) / 1048576:.2f} MB "
          f"({len(raw) / ROWS:.1f} B/row)\n", flush=True)
    with tenant_ctx(brazos):
        with Stage("1 extract (parse+stage)", ROWS):
            run = import_runs.extract(dana, {
                "target": import_runs.TARGET_ACCOUNTS, "source_kind": "file",
                "file_name": "accounts.csv", "content": text, "session_ref": "scale",
            })
        run_id = run["id"]
        with Stage("2 transform", ROWS):
            import_runs.transform(dana, run_id,
                                  {"mapping": ACCT_MAPPING, "row_handling": ALL_OFF})
        with Stage("3 validate", ROWS):
            import_runs.validate(dana, run_id)


# ── 4 · the byte cap, proved to be the binding limit ────────────────────────
def test_measure__the_byte_cap_refuses_before_the_row_cap(brazos, dana):
    _banner("WHICH CAP BINDS FIRST?")
    from core import errors
    n = 110_000
    text = premises_csv(n)
    raw = text.encode()
    print(f"  {n:,} premises rows = {len(raw):,} B "
          f"({len(raw) / 1048576:.2f} MB) — over BOTH caps", flush=True)
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            import_runs.extract(dana, {
                "target": import_runs.TARGET_PREMISES, "source_kind": "file",
                "file_name": "big.csv", "content": text, "session_ref": "scale",
            })
    print(f"  refused with: {caught.value.params if hasattr(caught.value, 'params') else ''} "
          f"{getattr(caught.value, 'message_key', '')}", flush=True)


# ── 5 · THE FILE THE OLD CAPS REFUSED: full TEMPLATE width at ROWS ──────────
def _template_file(target, n):
    """`n` rows at the shipped template's OWN width, built from `sample_csv`.

    Built from the template rather than invented so the width is the one the
    cap was measured against — a hand-written "wide" row is a guess about how
    wide a customer's file is; this is the product's own answer.
    """
    name, text = import_runs.sample_csv(target)
    lines = [line for line in text.splitlines() if line.strip()]
    header, samples = lines[0], lines[1:]
    reader = list(csv.reader(samples))
    fields = list(csv.reader([header]))[0]
    out = [header]
    for i in range(n):
        row = list(reader[i % len(reader)])
        for position, field in enumerate(fields):
            key = field.strip().lower()
            if "address" in key or "line" in key:
                row[position] = f"{1000 + i} {STREETS[i % len(STREETS)]} Suite {i % 40}"
            elif "external" in key or "legacy" in key:
                row[position] = f"LEG-{880000 + i}"
        out.append(",".join(
            f'"{cell}"' if ("," in cell or '"' in cell) else cell for cell in row))
    return "\n".join(out) + "\n"


def test_measure__premises_at_template_width(brazos, dana):
    _banner(f"PREMISES at SHIPPED TEMPLATE WIDTH · {ROWS:,} rows · stages 1-3\n"
            f"(this is the file the 10 MB cap REFUSED — CSV_BYTE_CAP is now "
            f"{import_runs.CSV_BYTE_CAP:,} B)")
    with tenant_ctx(brazos):
        text = _template_file(import_runs.TARGET_PREMISES, ROWS)
        raw = text.encode()
        print(f"  file: {len(raw):,} B = {len(raw) / 1048576:.2f} MB "
              f"({len(raw) / ROWS:.1f} B/row)   "
              f"old cap 10,485,760 B -> {'REFUSED' if len(raw) > 10*1048576 else 'accepted'}"
              f" · new cap {import_runs.CSV_BYTE_CAP:,} B -> "
              f"{'REFUSED' if len(raw) > import_runs.CSV_BYTE_CAP else 'ACCEPTED'}\n",
              flush=True)
        with Stage("1 extract (parse+stage)", ROWS):
            run = import_runs.extract(dana, {
                "target": import_runs.TARGET_PREMISES, "source_kind": "file",
                "file_name": "premises_template_width.csv", "content": text,
                "session_ref": "scale-wide",
            })
        run_id = run["id"]
        # the template maps ITSELF (DEF-616's property) — use what stage 1 detected
        detected = run.get("detected_mapping") or {}
        print(f"     detected mapping: {len(detected)} of "
              f"{len(run.get('headers') or [])} headers", flush=True)
        with Stage("2 transform", ROWS):
            import_runs.transform(dana, run_id,
                                  {"mapping": detected, "row_handling": ALL_OFF})
        with Stage("3 validate", ROWS):
            import_runs.validate(dana, run_id)
