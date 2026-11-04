# ADR-010 — Handset storage is SQLite, not IndexedDB

- **Status:** **Accepted; refined by ADR-022** (AD-17), which settles SQLite against a document store and fixes MMKV to preferences only.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-05**. Change request `CR-187-BRC10`.

## Context
The web field app stores its offline day in IndexedDB.

## Decision
SQLite on the handset (MMKV for small key state), carrying forward the existing store's schema and its per-technician partitioning.

## What it reverses
Nothing signed.

## Why
IndexedDB does not exist in React Native. The shape of the data is right; only the driver changes.

## Evidence
`expo-sqlite` and `react-native-mmkv` are in the scaffold (`field-app/package.json`).

## Cost
A new driver and its tests; `better-sqlite3` is a dev dependency so SQL is tested in Node.
