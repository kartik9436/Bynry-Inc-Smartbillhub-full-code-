"""G19 — no environment names in user-facing copy. Added 2026-08-11 from DEF-050.

THE DEFECT, AND WHY THE FIX THAT WAS MEANT TO CATCH IT DID NOT
---------------------------------------------------------------
`signinHelp.hint` reads *"The name your utility chose at signup — the part after
smartbillhub.bynry.com/"*. The live production host is typed into the copy, so
the sentence is wrong for every other deployment and **wrong in a way that reads
as correct to a reviewer sitting on that host**. The locale expansion then
multiplied it: the string lives in `en.json`, so all ten translations carry a
translation OF the hardcoded host. One wrong string became eleven.

DEF-050's escape reason is the part worth keeping: *"This is the SAME family as
the fix made on 2026-08-10, which replaced a hardcoded
`{{subdomain}}.smartbillhub.app`: that sweep searched for the DEAD domain and
therefore could not see the live one. **A search shaped by the bug you already
know about finds only that bug.**"*

That sentence is this gate's whole design constraint. It carries **no list of
domains**. It does not know what `smartbillhub.bynry.com` is, and it will not
know what the next host is called either. It matches the SHAPE of a host —
dot-separated labels ending in a letter-only label, a `scheme://` URL, a bare
`localhost[:port]`, an IPv4 literal — anywhere in any catalogue value, in any of
the eleven languages. Both DEF-050 and the 2026-08-10 instance it missed are
replayed as fixtures below, and the gate catches both.

WHY THE CATALOGUES AND NOT ALL OF THE CODE
-------------------------------------------
Every catalogue value is user-facing by definition, so precision there is exact:
the whole eleven-catalogue corpus produces five distinct matches, one of which is
the defect. The code side was MEASURED before being left out, and the numbers are
written down here so the next agent does not have to redo the measurement: the
same shape-based scan over every string literal in `07-frontend/src` and
`06-backend` (comments excluded) finds ZERO user-facing instances and three
structural false positives — the SVG XML namespace `http://www.w3.org/2000/svg`
(`apps/tenancy/logo.py`, and it MUST be that literal), the Django settings module
path `config.settings.local` (`manage.py`), and the i18n key
`signinHelp.invalid`, whose last label happens to be a real TLD. Everything else
it finds is a test fixture (`brazosbendutilities.com`, `evil.example`) or a test
asserting this very defect. A blocking check whose entire yield is three false
positives is the DEF-041 failure mode — *"a widened gate that fires on 40
legitimate items teaches people to add ALLOW entries"* — so the code side is
REPORTED here and not enforced. If a user-facing string ever ships outside the
catalogues, that is the change that should widen this gate.

WHAT IS NOT A FIX FOR A FINDING
--------------------------------
Adding a line to `ALLOWED` below. DEF-050's own prevention column calls the
durable half a GREP, not a review, and an allowlist entry is a review with extra
steps. The fix for a host in copy is to derive the host from configuration the
way `{{subdomain}}` already is, and then re-translate the one string. `ALLOWED`
exists for strings that merely LOOK like a host and are not one; each entry says
which, and adding one is a process event like editing `human_owned.txt`.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7)
------------------------------------------------
Part 0 replays three shapes against an in-memory copy of the real catalogues —
DEF-050's live host, the 2026-08-10 `{{subdomain}}.smartbillhub.app` the earlier
sweep was written for and could not see afterwards, and a bare `localhost:8000` —
and requires each to be reported. A fixture that fails to bite FAILS the gate.
Nothing is written to disk.

DEF-050's live instance is NOT fixed here: the string belongs to `en.json` and
the tenant-shell copy, and the fix is a code change (read the host from config)
plus ten re-translations. It is parked in `env_hostname_gaps.txt` against its own
defect row, LOUD on every run and EXPIRING the moment the string is fixed.

ADDING THIS GATE IS A PROCESS EVENT. G1-G16 are the PO-ratified merge-blocking
set (2026-08-11, option A); G19 is an Eng-Lead addition from DEF-050, reported
for the daily PO batch and recorded in 12-governance/02-decision-log.md.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

import csv
import io
import json
import re
from pathlib import Path

import common

LOCALES = common.REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales"
REGISTER = Path(__file__).resolve().parent / "env_hostname_gaps.txt"
DEFECT_LOG = common.REPO_ROOT / "12-governance" / "10-defect-log.csv"
CLOSED_STATUSES = {"fixed", "closed", "wontfix", "won't fix"}

MAX_NAMED = 3

#: A host-SHAPED token: labels joined by dots, last label letters only. No TLD
#: list and no domain list — see the docstring. The lookarounds keep it from
#: firing inside a longer identifier; `@` is deliberately NOT excluded, so
#: `support@some.host` is caught the same way a bare host is, and neither is a
#: leading `.` — without that, `{{subdomain}}.smartbillhub.app` (the 2026-08-10
#: instance, fixture A2) slips through on the dot after the interpolation, which
#: is the exact "the search only finds the bug it was shaped by" trap again.
#: Scanning is leftmost-longest, so a full `a.b.c` is still matched once, whole.
HOSTLIKE = re.compile(
    r"(?<![\w\-])((?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})(?![\w\-])",
    re.I,
)
#: The three shapes a dotted-label pattern cannot express.
SCHEME = re.compile(r"[a-z][a-z0-9+.\-]*://\S+", re.I)
LOOPBACK = re.compile(r"(?<![\w.\-])localhost(?::\d+)?(?![\w\-])", re.I)
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?![\w.])")

#: Strings that are host-SHAPED and are not hosts. Keyed by the matched token,
#: the way G15 keys its untranslated-value allowlist by value: an entry is a
#: human writing down that this particular string is not an environment.
#:
#: ⚠ An entry here is NOT how a finding is closed. See the docstring.
ALLOWED = {
    # The sign-in email PLACEHOLDER — sample data shown inside a field, not
    # prose and not a deployment. `utility.com` is nobody's host; G15 already
    # allowlists this exact string as sample data for the same reason.
    # Revisit if it is ever replaced by a real address.
    "alex@utility.com": "sample data in the sign-in email field (S3); also allowlisted by G15",
    # `audit.filter.actionHelp` quotes an audit ACTION CODE as an example of what
    # a user may type into the filter. An action code is dotted like a host and
    # is not one. The machine-translation pass TRANSLATED the code in three
    # catalogues — which is its own copy defect, and not this gate's to rule on;
    # each variant is named here so a new locale's variant needs a new line.
    # Revisit when the help copy stops quoting a literal code.
    "invoice.issued": "audit action code quoted as an example in audit.filter.actionHelp",
    "faktur.dikeluarkan": "the same audit action code, machine-translated (id-ID)",
    "fattura.emessa": "the same audit action code, machine-translated (it-IT)",
    "fatura.emitida": "the same audit action code, machine-translated (pt-BR)",
}


def catalogues() -> list[tuple[str, dict]]:
    if not LOCALES.is_dir():
        return []
    return [(p.name, json.loads(common.read_text(p))) for p in sorted(LOCALES.glob("*.json"))]


def hostlike(value: str) -> list[str]:
    """Every host-shaped token in one string, allowlisted ones removed."""
    found = HOSTLIKE.findall(value)
    found += [m.group(0) for m in SCHEME.finditer(value)]
    found += [m.group(0) for m in LOOPBACK.finditer(value)]
    found += [m.group(0) for m in IPV4.finditer(value)]
    # A URL contains its own host, so `https://x.example/a` matches twice; the
    # allowlist is checked against the WHOLE value too, so a sample email is
    # exempt however it was matched.
    return [f for f in dict.fromkeys(found) if f not in ALLOWED and value.strip() not in ALLOWED]


def findings(catalogue_pairs) -> list[tuple[str, str, str]]:
    """[(catalogue, key, matched token)] — every environment name in copy."""
    out = []
    for name, catalogue in catalogue_pairs:
        for key, value in catalogue.items():
            if not isinstance(value, str):
                continue
            for token in hostlike(value):
                out.append((name, key, token))
    return out


# ── the known-gap register (same discipline as G16's partition_exceptions) ──
def register() -> tuple[dict[tuple[str, str], tuple[str, str]], list[str]]:
    entries: dict[tuple[str, str], tuple[str, str]] = {}
    problems: list[str] = []
    if not REGISTER.is_file():
        return entries, ["env_hostname_gaps.txt is missing — the register must exist, even empty"]
    for lineno, raw in enumerate(common.read_text(REGISTER).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            problems.append(f"line {lineno}: expected `<key> <DEF-###> <YYYY-MM-DD> <reason>`")
            continue
        key, defect, date, reason = parts
        # ⚠ `\d{3,}` AND NOT `\d{3}` — DEF-1651, the same one-character bug
        # G18's register carried: a four-digit defect id is valid and was being
        # rejected as malformed, so nothing found after DEF-999 could be parked
        # here either. Fixed in the same diff because one wrong regex copied
        # into three files is one defect, and leaving two of them would leave
        # the finding half-true (hard-won law 5).
        if not re.fullmatch(r"DEF-(?:[A-Z]{3}-)?\d{3,}", defect):
            problems.append(f"line {lineno}: {key} must cite a DEF-### row, not {defect!r}")
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            problems.append(f"line {lineno}: {key} needs the date it was parked (YYYY-MM-DD)")
            continue
        entries[("*", key)] = (defect, reason)
    return entries, problems


def defect_rows() -> dict[str, str]:
    if not DEFECT_LOG.is_file():
        return {}
    # io.StringIO, not splitlines(): the log's free-text columns carry embedded
    # newlines and a line-based reader would silently invent rows.
    reader = csv.DictReader(io.StringIO(common.read_text(DEFECT_LOG)))
    return {(r.get("id") or "").strip(): (r.get("status") or "").strip().lower() for r in reader}


# ═══════════════════════════════════════════════════════════════════════════
# PART 0 — SELF-TEST (law 7). The live defect is parked, so a green run proves
# the register works and not that the detector does. Each fixture plants a host
# in an in-memory copy of the real `en.json`.
# ═══════════════════════════════════════════════════════════════════════════
FIXTURES = [
    ("A1", "g19.probe.live",
     "The name your utility chose at signup — the part after smartbillhub.bynry.com/",
     "DEF-050 itself: the LIVE production host typed into sign-in help copy"),
    ("A2", "g19.probe.dead",
     "Your utility's address is {{subdomain}}.smartbillhub.app",
     "the 2026-08-10 instance — the one the earlier sweep was written FOR and "
     "could not see afterwards, because it searched for the domain by name"),
    ("A3", "g19.probe.loopback",
     "Open http://localhost:8000/ to continue",
     "a developer host in shipped copy: no dot-labelled domain at all"),
]


def self_test(catalogue_pairs) -> list[tuple[str, bool, str]]:
    results = []
    base = dict(catalogue_pairs[0][1]) if catalogue_pairs else {}
    for tag, key, value, why in FIXTURES:
        probed = dict(base)
        probed[key] = value
        hits = [t for name, k, t in findings([("probe.json", probed)]) if k == key]
        results.append((tag, bool(hits),
                        f"{value[:48]}… -> " + (f"reported {hits[0]!r}" if hits
                                                else f"NOT reported (expected FAIL) — {why}")))
    return results


def run() -> tuple[str, str]:
    catalogue_pairs = catalogues()
    if not catalogue_pairs:
        return "SKIP", f"no locale catalogue in {LOCALES.name}/ — nothing user-facing to scan"

    blind = [(tag, detail) for tag, ok, detail in self_test(catalogue_pairs) if not ok]
    if blind:
        return "FAIL", (f"self-test BLIND: {blind[0][0]} {blind[0][1]}. A guard that cannot be "
                        "shown to fail is not a guard (law 7).")

    entries, problems = register()
    statuses = defect_rows()
    for (_, key), (defect, _reason) in sorted(entries.items()):
        if defect not in statuses:
            problems.append(f"{key} cites {defect}, which has no row in the defect log")
        elif statuses[defect] in CLOSED_STATUSES:
            problems.append(f"{key} cites {defect}, which is {statuses[defect]} — the reason to "
                            "be parked has expired; the copy must be fixed or the row re-filed")

    found = findings(catalogue_pairs)
    parked_keys = {key for _, key in entries}
    new = [f"{name}:{key} names {token!r}" for name, key, token in found if key not in parked_keys]
    hit_keys = {key for _, key, _ in found}
    stale = sorted(key for key in parked_keys if key not in hit_keys)

    failures = []
    if new:
        failures.append(f"{len(new)} catalogue value(s) name an environment: "
                        f"{common.summarize(new, MAX_NAMED)} — derive the host from configuration "
                        "the way {{subdomain}} already is; do NOT add an ALLOWED entry")
    if stale:
        failures.append(f"{len(stale)} STALE register entry(ies) — the copy no longer names a "
                        f"host, delete the line: {common.summarize(stale, MAX_NAMED)}")
    failures += problems
    if failures:
        return "FAIL", f"{len(failures)} problem(s): " + common.summarize(failures, 2)

    values = sum(len(c) for _, c in catalogue_pairs)
    return "PASS", (
        f"{values} value(s) across {len(catalogue_pairs)} catalogue(s) name no host, URL, "
        f"localhost or IP ({len(ALLOWED)} host-shaped string(s) allowlisted as not-a-host); "
        f"{len(parked_keys)} key(s) PARKED in env_hostname_gaps.txt; "
        f"self-test: {len(FIXTURES)}/{len(FIXTURES)} shapes bite"
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    print()
    print("--- Part 0: self-test (law 7 — prove the guard goes RED before trusting it green) ---")
    for tag, ok, text in self_test(catalogues()):
        print(f"  {'BITES' if ok else 'BLIND'} {tag}  {text}")
    print()
    print("--- findings ---")
    for name, key, token in findings(catalogues()):
        print(f"  {name}:{key} -> {token!r}")
    raise SystemExit(0 if status != "FAIL" else 1)
