Steps 4 and 5 AFTER DEF-CUS-7910 and DEF-CUS-7911
lane NCT-01 · 2026-09-29 · version 2.410.6

WHY THIS FOLDER EXISTS BESIDE built-2026-09-29-five-steps/
-----------------------------------------------------------
Lane NC5-PHOTOS photographed all five steps earlier the same day and filed
four defects from what the pictures showed. Two of them were on these two
screens and are now fixed. Their photographs are NOT replaced and must not
be: they are the EVIDENCE for DEF-CUS-7910 and DEF-CUS-7911, cited by
DIVERGENCES-steps-4-5.md, and a defect's evidence is worth less the moment
somebody overwrites it with the fix. These are the after.

  step4-charges-1440.png   1440 x 1440
  step4-charges-1280.png   1280 x 1440
  step5-review-1440.png    1440 x 2633
  step5-review-1280.png    1280 x 2674

WHAT CHANGED BETWEEN THE TWO SETS
---------------------------------
DEF-CUS-7910 — the review drew "Who we are telling" and "Messages" TWICE.
  NewConnectWizard mounted the whole old Communication panel underneath the
  review, under a comment reading "until the REVIEW lane draws it there" —
  which it had. One of each now. The screen is 693px shorter for it, which
  is the cleanest measure of how much was duplicated.

DEF-CUS-7911 — the review's charge table had CHARGE · BASIS · QTY and
  stopped, so the last screen before Create never said what a charge costs.
  EACH and AMOUNT are drawn now, from the same cached quote-preview step 4
  reads, through the same money cell. An unpriced line is BLANK, never
  $0.00.

HOW THEY WERE TAKEN, AND ONE THING TO KNOW BEFORE COMPARING
------------------------------------------------------------
Chromium against a booted stack, signed in as Dana at Brazos Bend, by
10-scripts/nct_steps45_walkthrough.mjs. The Create button was never pressed,
so nothing was written.

The build is EMPTY — no units, no services, no charges — because this walk
starts a fresh draft rather than filling one. So the counts read 0 and the
money lines are blank BY DESIGN: these shots prove the STRUCTURE and the
absences. For the same screens with real data in them, use NC5-PHOTOS's
six-unit build in built-2026-09-29-five-steps/.

step5-review-*.png is shot with "Choosing a template" OPEN, because the walk
presses + Add template to prove the picker opens before it shoots.

⚠ fullPage: true DOES NOT CAPTURE THIS APP, and this walk used it until
today. .app-shell is height:100vh/overflow:hidden with .view scrolling
inside, so the document never grows and fullPage returns the fold — 1400px
of a 3326px screen, silently, with nothing in the output to say so. That is
how DEF-CUS-7910 hid: the duplicate was below the crop. shot() now scrolls
every scroller to the top, grows the VIEWPORT to the tallest scroll height
and PRINTS each image's dimensions, so a truncated capture is visible in the
log instead of only in the pixels. NC5-PHOTOS found the same trap
independently and says so in its own README.
