# Status reports — one file per request, dated, never overwritten

Every status table the Product Owner asks for is written here as a file, at the
moment it is produced, alongside the exact commands that produced it.

**Why this folder exists.** A module table was produced in an earlier session,
pasted into chat and never saved. When the PO asked for it again the numbers
could not be reproduced and the definitions behind them were gone — so the next
table was a fresh opinion rather than a comparison. That is hard-won law 10 in
its purest form, and this folder is the fix.

**The rules:**

1. **One file per request, named `YYYY-MM-DD-<subject>.md`.** Never overwrite an
   earlier report — a wrong number that was corrected later is part of the
   record, not an embarrassment to be tidied away.
2. **Every table names the command that produced it.** A number nobody can
   re-run is an assertion, not a measurement.
3. **Corrections are appended to the report they correct**, with the date and
   what was wrong. Three numbers were wrong today and each was caught by the PO
   or a lane disbelieving it, not by any automated check — so the corrections
   are the most useful thing in here.
4. **State what a measurement cannot see.** Every script here has limits and
   they belong beside the figure, not in a footnote nobody reads.

## The measurements, and what each is for

| Command | Answers |
|---|---|
| `python3 10-scripts/r2_status.py` | Per module, in build order: routes, engine lines, screens, test cases, journeys |
| `python3 10-scripts/module_report.py` | Per module: stories declared / touched / built / proved. `--vs <commit>` compares two points |
| `python3 10-scripts/screen_report.py` | Screens each module owns, and screens NO story owns. Deliberately has no "done" column |
| `python3 10-scripts/defect_report.py` | The defect register, by module and severity |
| `python3 10-scripts/gates/run_gates.py` | The merge-blocking gates |
| `cat 10-scripts/gates/surface_debt.txt` | Stories built with no way for a person to reach them |

**For "how much is left", read STORIES, not screens.** Screens carry no id in
code, the inventory has no module column, and one screen is claimed by many
stories — so any screen-completion score is arbitrary. That was established the
hard way, in three failed attempts, on 2026-08-16.
