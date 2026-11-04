# ADR-009 — One clean line between what the field app does offline and what needs a signal

- **Status:** **Accepted.** Rests on rule R31 (PO ruled: *"The map requires a signal"*) and R16/R19 (PO ruled: money is read, and pushed when it changes).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-04**. Change request `CR-187-BRC10`.

## Context
A whole shift can pass with no signal. Every screen has to know which side of the line it is on.

## Decision
**Offline-first:** the day and week · job open · safety gate · tasks · checklists · readings · photos, watermark and GPS · signature · debrief · parts · close · field-raised orders (queued) · SOPs · barcode scanning · asset history (cached).

**Online only:** the map · navigation hand-off · live balance and tariff · the cleared-payment check and restoration countdown · mid-day re-sequencing · nearby work and claiming · push and alerts.

**In one line:** everything a technician DOES is offline; everything they LOOK UP about money or position is online.

## What it reverses
Nothing.

## Why
Capture must never depend on the network; money and position are only true when they are current.

## Evidence
Walkthrough E2E-02 (the whole day offline) and E2E-12 (disconnect with no signal) are written against this line.

## Cost
The online-only screens each need an offline state (R31: the map shows an offline state; the address travels offline with the job).
