# ADR-017 — A drawer, with quick tabs at the bottom

- **Status:** **Accepted in part.** The drawer and the always-on-screen sync number stand. **The bottom bar's contents are SUPERSEDED** — first by rule R102 (PO ruled: *"Two tabs, Jobs and Reads"*), then by ADR-027 (AD-22: *Home · Jobs · Reads*, as every phone drawing shows). Which of those two holds is `OQ-FLD-12799`.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-12**. Change request `CR-187-BRC10`.

## Context
A technician moves between the day, a job, the map and their own records many times an hour.

## Decision
Drawer holds **Work** (Today · Completed · Map · Assets · Alerts) and **Me** (Profile · Admin · Shifts · Timesheet · Van · Sync). As first drawn, the bottom bar carried Today and Alerts only. **Always on screen:** the sync number with its connection icon (R32), and the availability chip. **Tablet:** the drawer becomes a permanent sidebar and the list sits beside its detail.

## What it reverses
Nothing signed. Its own bottom bar was overtaken as described under Status.

## Why
The sync number is what a technician checks most often; R103 (PO ruled) puts it one tap from the day.

## Evidence
Phone boards FF-09 Menu and FF-10 Today.

## Cost
A tablet frame with measured pane widths (R121/R122).
