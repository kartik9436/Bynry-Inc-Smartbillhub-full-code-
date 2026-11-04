#!/usr/bin/env python3
"""Prove tenant isolation for real, and record what happened.

WHY THIS IS A SCRIPT AND NOT PART OF THE GATE
----------------------------------------------
`G5` is the merge gate for hard rule 1, and until 2026-09-05 it ran
`pytest -m isolation` inline with no settings override — which picks up the
in-memory sqlite pinned in `pyproject.toml`, where row-level security does not
exist. Four fifths of the suite skipped itself and the gate reported PASS
(`DEF-GOV-4024`).

Pointing it at real PostgreSQL fixes the lie and costs **about fourteen
minutes** with the test database reused. `run_gates.py` is what a lane runs
before every merge, several times an hour, on a machine that has carried eight
lanes at once. A gate that costs a quarter of an hour is a gate lanes stop
running — and a check nobody runs is worth exactly what a check that cannot fail
is worth, which is the thing this whole episode was about.

⚠ **MEASURED 2026-09-25: SIXTEEN MINUTES, NOT NINETY — AND THE NINETY IS WHERE
THE ARGUMENT ABOVE HAS BEEN COMING FROM.** The only receipt this repo held was
taken 2026-09-07 and recorded `5345.09s (1:29:05)`, and that figure is the one
quoted back in the defect register and in `G5`'s own stale-proof message
(*"about 20 minutes"*, *"about ninety minutes"*). A completed run on real
PostgreSQL 16 on 2026-09-25 — 296 selected, `--reuse-db`, warm database — took
**976.27s (16:16)**. The 1:29:05 was a COLD run paying for 435 migrations; the
fourteen-minute estimate in the paragraph above was right all along.

**WHY THAT IS WRITTEN HERE AND NOT ACTED ON: it is the Eng-Lead's call, not a
lane's.** Sixteen minutes is still *a quarter of an hour*, which is exactly the
cost this paragraph refuses — so the measurement does not by itself move this
script inside `run_gates.py`. What it does remove is the belief that the run
costs an hour and a half, which is the number anybody re-deciding this would
have found. The decision is whether a sixteen-minute wave-close act should
become a merge-gate act; the input is now correct.

(`OQ-GOV-12655` asked whether `G5` could report green at all on a
correctly-provisioned cluster, because the `def639` canary skipped wherever the
app role could not bypass row-level security, and `G5` fails on any skip. Since
`b92cb6393` the canary contrasts the probe against the policy itself and skips
on neither kind of role. Measured 2026-10-02 as a NOSUPERUSER NOBYPASSRLS role,
on a test database built fresh for a new migration digest: **352 passed, 0
failed, 0 skipped in 1724.26s (28:44)**, and `G5` read PASS. The register row
is left for its owner to close; the premise it was raised on no longer holds.)

So the run is an explicit act, here, and its result is written to
`12-governance/isolation-receipt.json`. `G5` reads that receipt and reports
whether a CURRENT proof exists. The receipt names the migration digest it was
taken against, so a proof cannot outlive the schema it proved: add a migration
and it is stale by definition, the gate says so, and nobody has to remember.

WHAT IT NEEDS
-------------
A PostgreSQL role that row-level security genuinely applies to — NOT a superuser,
because a superuser bypasses every policy and the deny is never evaluated — and
which may `SET ROLE` into the probe role. An administrator does it once:

    CREATE ROLE sbh_rls_probe NOLOGIN NOSUPERUSER NOBYPASSRLS;
    CREATE ROLE sbh_gate_iso LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE
      NOREPLICATION CREATEDB PASSWORD 'sbh_gate_iso';
    GRANT sbh_rls_probe TO sbh_gate_iso WITH ADMIN OPTION;

Then either set `SBH_GATE_DATABASE_URL`, or rely on the probed fallbacks in
`10-scripts/gates/g05_isolation.py`.

WHAT IT RECORDS, AND WHAT THAT IS WORTH
----------------------------------------
A receipt is a RECORD, not an attestation: it is written by whoever ran the
thing, exactly like `G12`'s browser-run receipt. What it cannot do — and what
the old arrangement did every single day — is report a pass over a suite that
never ran.

A refusal is never recorded. If no usable database is found, or the probe role
could not be put in place, the receipt is left exactly as it was and the reason
is printed instead, because a proof that did not happen must not overwrite one
that did.

⚠ **AND UNTIL 2026-09-25 THAT SENTENCE DID NOT HOLD ON INTERRUPTION
(`DEF-GOV-6704`).** It covered the two refusals above and nothing else, so a run
that STARTED and was killed — which this container does routinely, three
restarts in a few hours on the day this was found — wrote a receipt saying
`"summary": "no output"`, `passed 0, failed 0, skipped 0`, **dated today and at
the current migration digest**, over the 2026-09-07 proof of 272 passing cases.
`G5` reads 0 failures and 0 skips as a PASS, and answered, verbatim:

    PASS: isolation proved on 2026-09-25 09:30 UTC as smartbillhub, a role
    genuinely subject to RLS, against these exact migrations: no output

So the last real proof was one interrupted run away from becoming a green lie,
on **hard rule 1**. That is hard-won law 1 exactly — a comment claiming a
guarantee is not the guarantee — written by the very file that promised it.
`g05_isolation.prove()` now refuses to hand back a receipt when the run printed
no counts, exited on something that is not a pytest verdict, or finished with
zero passing cases; the reasoning and the reproduction are in its own comment.

⚠ **AND THE RECEIPT MUST NAME ITS FAILING CASES, NOT ONLY COUNT THEM.** The
2026-09-07 receipt said *"1 failed"* and named nothing, so there was nothing to
trace and nobody could say whether that case was still failing — which is why it
stood unanswered for eighteen days. The run is taken with `-rfEs` and the
receipt carries `failing_cases`, pytest's own `FAILED`/`ERROR` lines. A count
with no name is not a record anybody can act on.

⚠ **AND A RECORD THAT LIVES ONLY INSIDE THE REPOSITORY IS ONE ROUTINE HYGIENE
STEP FROM GONE — `DEF-GOV-6962`, 2026-09-27.** `12-governance/isolation-receipt.json`
is a tracked file. A checkout refresh, a stale-tree restore, a `git show <tip>:…
> …` — every recovery this project's own hard-won law 12 prescribes — writes the
BRANCH's copy over whatever is on disk. On 2026-09-27 a **67-minute** run
finished FAIL (9 failed, 11 errored, 301 passed) and its receipt was destroyed
minutes later by exactly that. The counts survived in a lane's notes; the
**names of the twenty cases did not**, which is the one thing the receipt exists
to carry. `12-governance/isolation-reproof-2026-09-25.md` §4 recorded this class
of loss two days earlier from an interrupted run; half of what it proposed was
built (`prove()` now refuses to build a receipt from a run with no counts) and
this half was not.

**So a finished run is written TWICE, and the second copy is outside the
working tree.** `~/.smartbillhub/isolation-runs/<taken_on>.json`, overridable
with `SBH_ISOLATION_ARCHIVE`, one file per run, never overwritten and never
pruned. It is deliberately NOT in the scratchpad: the scratchpad is
session-scoped and dies with the container, which is the same class of loss one
step along. A run takes an hour; an archive file is 2 KB.

⚠ **AND THE RECEIPT IS NOT OVERWRITTEN BY SOMETHING WORSE THAN ITSELF.** The
in-repo receipt is refused where the new run is OLDER than the one already
recorded — which is what a restored-from-branch copy plus a re-run of an old
checkout looks like — or where it reports no cases at all. The archive is
written FIRST and unconditionally, so a refusal here loses nothing: the run is
already on disk somewhere a checkout cannot reach, and the message says where.
**A guard that discards the evidence it is guarding is not a guard.**
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "gates"))

import g05_isolation as g5  # noqa: E402

#: Where the durable copy goes. OUTSIDE the repository, on purpose — see the
#: header. `SBH_ISOLATION_ARCHIVE` overrides it for a machine with no writable
#: home directory; an unwritable archive is reported, never fatal, because a
#: proof that cannot be filed is still a proof that was taken.
ARCHIVE = Path(os.environ.get("SBH_ISOLATION_ARCHIVE")
               or (Path.home() / ".smartbillhub" / "isolation-runs"))

#: `taken_on` is written by `g05_isolation.prove()` as `%Y-%m-%d %H:%M UTC`.
#: Parsed rather than string-compared: the formats have moved before, and a
#: comparison that silently means "alphabetically later" is law 7's *incapable
#: of failing* shape wearing a plausible face.
_TAKEN_ON = "%Y-%m-%d %H:%M UTC"


def taken_at(receipt: dict) -> datetime | None:
    """When a receipt says its run finished, or None if it does not say."""
    raw = str(receipt.get("taken_on") or "").strip()
    try:
        return datetime.strptime(raw, _TAKEN_ON).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def cases_in(receipt: dict) -> int:
    """How many cases the run actually reported, in any state."""
    return sum(int(receipt.get(name) or 0)
               for name in ("passed", "failed", "errors", "skipped"))


def archive(receipt: dict) -> Path | None:
    """Write the durable copy. Returns where, or None with a printed reason.

    One file per run, named for the run rather than for the file it is a copy
    of, so two runs can never land on the same name and nothing here overwrites
    anything. `:` is not in the name — it is legal on this filesystem and is not
    on every one a receipt might be copied to.
    """
    stamp = re.sub(r"[^0-9A-Za-z]+", "-", str(receipt.get("taken_on") or "undated")).strip("-")
    try:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        out = ARCHIVE / f"isolation-{stamp}.json"
        # `x` — never clobber. A second run within the same MINUTE gets a
        # suffix rather than silently replacing the first.
        for attempt in range(1, 100):
            try:
                with out.open("x", encoding="utf-8") as handle:
                    json.dump(receipt, handle, indent=2, sort_keys=True)
                    handle.write("\n")
                return out
            except FileExistsError:
                out = ARCHIVE / f"isolation-{stamp}-{attempt}.json"
        return None
    except OSError as exc:
        print(f"\ncould NOT write the durable copy to {ARCHIVE}: {exc}")
        print("the run still happened; set SBH_ISOLATION_ARCHIVE to a writable directory.")
        return None


def main() -> int:
    status, detail, receipt = g5.prove()
    print(f"{status}: {detail}")
    if receipt is None:
        print("\nnothing recorded — the suite did not run, and a refusal is not a proof.")
        return 1

    # ── the durable copy goes FIRST and unconditionally ───────────────────────
    # Everything below can refuse. Nothing below can lose the run.
    kept = archive(receipt)
    if kept is not None:
        print(f"\nthe full run is archived at {kept} — outside the repository, so a "
              f"checkout refresh cannot reach it (DEF-GOV-6962).")

    # ── the in-repo receipt is not overwritten by something worse ─────────────
    if cases_in(receipt) == 0:
        print(f"\nNOT written to {g5.RECEIPT.relative_to(g5.common.REPO_ROOT)}: this run "
              f"reports no cases in any state, so it says nothing about the code and would "
              f"replace a receipt that does. The last real proof is left exactly as it was.")
        return 1

    existing = None
    if g5.RECEIPT.exists():
        try:
            existing = json.loads(g5.RECEIPT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
    if isinstance(existing, dict):
        was, now = taken_at(existing), taken_at(receipt)
        if was is not None and now is not None and now < was:
            print(f"\nNOT written to {g5.RECEIPT.relative_to(g5.common.REPO_ROOT)}: this run "
                  f"finished {receipt.get('taken_on')} and the recorded one finished "
                  f"{existing.get('taken_on')}, which is LATER. An older proof does not "
                  f"replace a newer one — that is what a stale checkout re-running an old "
                  f"tree looks like from here. The archived copy above holds this run.")
            return 1

    g5.RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    g5.RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nrecorded in {g5.RECEIPT.relative_to(g5.common.REPO_ROOT)} — "
          f"G5 will read it until the migrations change.")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
