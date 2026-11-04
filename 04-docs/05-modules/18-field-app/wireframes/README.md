# Field app wireframes — the screens to build FROM, as images

Rendered on 2026-10-21 from the *SMART360 Next Field App* design canvas (claude.ai artifact, version `1792586755-e39d`) with the canvas's own runtime, at each board's drawn size, 1× scale.

**These images ARE the specification for every field-app screen** (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Open the PNG and look at it. Text extracted from the design is an index, never the spec. B14 rules 44 and 45 decide construction: sizes, spacing and touch targets come from the token module and the native type ramp, never from a pixel in a picture (rule 37).

**185 images:** phone 64 (FF-01..FF-63 + the theme switch), tablet 92 (FF-01..63 T + RW-01..29 T), reads 29 (RW-01..29).

To re-render after the design changes: read the canvas's `project/*.dc.html` and `artifact-type/dc-runtime.js` (served as `support.js`) and screenshot each board at its `canvas.json` frame size with Playwright and the pre-installed Chromium.

| Screen | Image | Size | Design board |
|---|---|---|---|
| FF-01 Splash | [`phone/FF-01-splash.png`](phone/FF-01-splash.png) | 390×844 | `Splash.dc.html` |
| FF-02 Intro 1 | [`phone/FF-02-intro-1.png`](phone/FF-02-intro-1.png) | 390×844 | `Intro1.dc.html` |
| FF-03 Intro 2 | [`phone/FF-03-intro-2.png`](phone/FF-03-intro-2.png) | 390×844 | `Intro2.dc.html` |
| FF-04 Intro 3 | [`phone/FF-04-intro-3.png`](phone/FF-04-intro-3.png) | 390×844 | `Intro3.dc.html` |
| FF-05 Sign in | [`phone/FF-05-sign-in.png`](phone/FF-05-sign-in.png) | 390×844 | `SignIn.dc.html` |
| FF-06 Forgot password | [`phone/FF-06-forgot-password.png`](phone/FF-06-forgot-password.png) | 390×844 | `Forgot.dc.html` |
| FF-07 Permissions | [`phone/FF-07-permissions.png`](phone/FF-07-permissions.png) | 390×844 | `Permissions.dc.html` |
| FF-08 First sync | [`phone/FF-08-first-sync.png`](phone/FF-08-first-sync.png) | 390×844 | `FirstSync.dc.html` |
| FF-09 Menu | [`phone/FF-09-menu.png`](phone/FF-09-menu.png) | 390×844 | `Drawer.dc.html` |
| FF-10 Today | [`phone/FF-10-today.png`](phone/FF-10-today.png) | 390×844 | `Main.dc.html` |
| FF-11 Nearby | [`phone/FF-11-nearby.png`](phone/FF-11-nearby.png) | 390×844 | `Nearby.dc.html` |
| FF-12 Claim | [`phone/FF-12-claim.png`](phone/FF-12-claim.png) | 390×844 | `Claim.dc.html` |
| FF-13 Map | [`phone/FF-13-map.png`](phone/FF-13-map.png) | 390×844 | `Map.dc.html` |
| FF-14 Stop | [`phone/FF-14-stop.png`](phone/FF-14-stop.png) | 390×844 | `Stop.dc.html` |
| FF-15 Job | [`phone/FF-15-job.png`](phone/FF-15-job.png) | 390×844 | `Job.dc.html` |
| FF-16 Safety | [`phone/FF-16-safety.png`](phone/FF-16-safety.png) | 390×844 | `Safety.dc.html` |
| FF-17 Tasks | [`phone/FF-17-tasks.png`](phone/FF-17-tasks.png) | 390×844 | `Tasks.dc.html` |
| FF-18 Add step | [`phone/FF-18-add-step.png`](phone/FF-18-add-step.png) | 390×844 | `AddStep.dc.html` |
| FF-19 Checklist | [`phone/FF-19-checklist.png`](phone/FF-19-checklist.png) | 390×844 | `Checklist.dc.html` |
| FF-20 Readings | [`phone/FF-20-readings.png`](phone/FF-20-readings.png) | 390×844 | `Readings.dc.html` |
| FF-21 Photos | [`phone/FF-21-photos.png`](phone/FF-21-photos.png) | 390×844 | `Photos.dc.html` |
| FF-22 Compare | [`phone/FF-22-compare.png`](phone/FF-22-compare.png) | 390×844 | `Compare.dc.html` |
| FF-23 Materials | [`phone/FF-23-materials.png`](phone/FF-23-materials.png) | 390×844 | `Materials.dc.html` |
| FF-24 Parts used | [`phone/FF-24-parts-used.png`](phone/FF-24-parts-used.png) | 390×844 | `Parts.dc.html` |
| FF-25 Customer | [`phone/FF-25-customer.png`](phone/FF-25-customer.png) | 390×844 | `Customer.dc.html` |
| FF-26 Restoration | [`phone/FF-26-restoration.png`](phone/FF-26-restoration.png) | 390×844 | `Restoration.dc.html` |
| FF-27 Stale money | [`phone/FF-27-stale-money.png`](phone/FF-27-stale-money.png) | 390×844 | `Disconnect.dc.html` |
| FF-28 Documents | [`phone/FF-28-documents.png`](phone/FF-28-documents.png) | 390×844 | `Documents.dc.html` |
| FF-29 Crew | [`phone/FF-29-crew.png`](phone/FF-29-crew.png) | 390×844 | `Crew.dc.html` |
| FF-30 Notes | [`phone/FF-30-notes.png`](phone/FF-30-notes.png) | 390×844 | `Notes.dc.html` |
| FF-31 Activity | [`phone/FF-31-activity.png`](phone/FF-31-activity.png) | 390×844 | `Activity.dc.html` |
| FF-32 Debrief | [`phone/FF-32-debrief.png`](phone/FF-32-debrief.png) | 390×844 | `Debrief.dc.html` |
| FF-33 Signature | [`phone/FF-33-signature.png`](phone/FF-33-signature.png) | 390×844 | `Signature.dc.html` |
| FF-34 Close | [`phone/FF-34-close.png`](phone/FF-34-close.png) | 390×844 | `Close.dc.html` |
| FF-35 Completed | [`phone/FF-35-completed.png`](phone/FF-35-completed.png) | 390×844 | `Completed.dc.html` |
| FF-36 Reopen | [`phone/FF-36-reopen.png`](phone/FF-36-reopen.png) | 390×844 | `Reopen.dc.html` |
| FF-37 Raise | [`phone/FF-37-raise.png`](phone/FF-37-raise.png) | 390×844 | `Raise.dc.html` |
| FF-38 Scan | [`phone/FF-38-scan.png`](phone/FF-38-scan.png) | 390×844 | `Scan.dc.html` |
| FF-39 Asset | [`phone/FF-39-asset.png`](phone/FF-39-asset.png) | 390×844 | `Asset.dc.html` |
| FF-40 Asset history | [`phone/FF-40-asset-history.png`](phone/FF-40-asset-history.png) | 390×844 | `History.dc.html` |
| FF-41 Asset search | [`phone/FF-41-asset-search.png`](phone/FF-41-asset-search.png) | 390×844 | `Search.dc.html` |
| FF-42 Alerts | [`phone/FF-42-alerts.png`](phone/FF-42-alerts.png) | 390×844 | `Alerts.dc.html` |
| FF-43 Emergency | [`phone/FF-43-emergency.png`](phone/FF-43-emergency.png) | 390×844 | `Emergency.dc.html` |
| FF-44 Profile | [`phone/FF-44-profile.png`](phone/FF-44-profile.png) | 390×844 | `Profile.dc.html` |
| FF-45 Availability | [`phone/FF-45-availability.png`](phone/FF-45-availability.png) | 390×844 | `Availability.dc.html` |
| FF-46 Shifts | [`phone/FF-46-shifts.png`](phone/FF-46-shifts.png) | 390×844 | `Shifts.dc.html` |
| FF-47 Timesheet | [`phone/FF-47-timesheet.png`](phone/FF-47-timesheet.png) | 390×844 | `Timesheet.dc.html` |
| FF-48 Admin tasks | [`phone/FF-48-admin-tasks.png`](phone/FF-48-admin-tasks.png) | 390×844 | `Admin.dc.html` |
| FF-49 Van | [`phone/FF-49-van.png`](phone/FF-49-van.png) | 390×844 | `Van.dc.html` |
| FF-50 Sync | [`phone/FF-50-sync.png`](phone/FF-50-sync.png) | 390×844 | `Sync.dc.html` |
| FF-51 Settings | [`phone/FF-51-settings.png`](phone/FF-51-settings.png) | 390×844 | `Settings.dc.html` |
| FF-52 Notifications | [`phone/FF-52-notifications.png`](phone/FF-52-notifications.png) | 390×844 | `Notifications.dc.html` |
| FF-53 Sign out | [`phone/FF-53-sign-out.png`](phone/FF-53-sign-out.png) | 390×844 | `Logout.dc.html` |
| FF-54 Dark theme | [`phone/FF-54-dark-theme.png`](phone/FF-54-dark-theme.png) | 390×844 | `Night.dc.html` |
| FF-55 Sunlight theme | [`phone/FF-55-sunlight-theme.png`](phone/FF-55-sunlight-theme.png) | 390×844 | `Sunlight.dc.html` |
| RW-01 My routes | [`reads/RW-01-my-routes.png`](reads/RW-01-my-routes.png) | 390×844 | `RWRoutes.dc.html` |
| RW-02 Route summary | [`reads/RW-02-route-summary.png`](reads/RW-02-route-summary.png) | 390×844 | `RWSummary.dc.html` |
| RW-03 Download | [`reads/RW-03-download.png`](reads/RW-03-download.png) | 390×844 | `RWDownload.dc.html` |
| RW-04 Route map | [`reads/RW-04-route-map.png`](reads/RW-04-route-map.png) | 390×844 | `RWMap.dc.html` |
| RW-05 The walk | [`reads/RW-05-the-walk.png`](reads/RW-05-the-walk.png) | 390×844 | `RWWalk.dc.html` |
| RW-06 The stop | [`reads/RW-06-the-stop.png`](reads/RW-06-the-stop.png) | 390×844 | `RWStop.dc.html` |
| RW-07 Getting in | [`reads/RW-07-getting-in.png`](reads/RW-07-getting-in.png) | 390×844 | `RWAccess.dc.html` |
| RW-08 Find a meter | [`reads/RW-08-find-a-meter.png`](reads/RW-08-find-a-meter.png) | 390×844 | `RWFind.dc.html` |
| RW-09 Read entry | [`reads/RW-09-read-entry.png`](reads/RW-09-read-entry.png) | 390×844 | `RWRead.dc.html` |
| RW-10 Dials | [`reads/RW-10-dials.png`](reads/RW-10-dials.png) | 390×844 | `RWDials.dc.html` |
| RW-11 Scan to confirm | [`reads/RW-11-scan-to-confirm.png`](reads/RW-11-scan-to-confirm.png) | 390×844 | `RWScan.dc.html` |
| RW-12 Master and subs | [`reads/RW-12-master-and-subs.png`](reads/RW-12-master-and-subs.png) | 390×844 | `RWSubmeters.dc.html` |
| RW-13 The reading | [`reads/RW-13-the-reading.png`](reads/RW-13-the-reading.png) | 390×844 | `RWRecord.dc.html` |
| RW-14 The camera | [`reads/RW-14-the-camera.png`](reads/RW-14-the-camera.png) | 390×844 | `RWCamera.dc.html` |
| RW-15 High or low | [`reads/RW-15-high-or-low.png`](reads/RW-15-high-or-low.png) | 390×844 | `RWChallenge.dc.html` |
| RW-16 Second look | [`reads/RW-16-second-look.png`](reads/RW-16-second-look.png) | 390×844 | `RWReread.dc.html` |
| RW-17 Can't read | [`reads/RW-17-can-t-read.png`](reads/RW-17-can-t-read.png) | 390×844 | `RWCantRead.dc.html` |
| RW-18 Different meter | [`reads/RW-18-different-meter.png`](reads/RW-18-different-meter.png) | 390×844 | `RWWrongMeter.dc.html` |
| RW-19 Not on the route | [`reads/RW-19-not-on-the-route.png`](reads/RW-19-not-on-the-route.png) | 390×844 | `RWScanOff.dc.html` |
| RW-20 Add a meter | [`reads/RW-20-add-a-meter.png`](reads/RW-20-add-a-meter.png) | 390×844 | `RWAddMeter.dc.html` |
| RW-21 Raise it | [`reads/RW-21-raise-it.png`](reads/RW-21-raise-it.png) | 390×844 | `RWRaise.dc.html` |
| RW-22 Where you are | [`reads/RW-22-where-you-are.png`](reads/RW-22-where-you-are.png) | 390×844 | `RWProgress.dc.html` |
| RW-23 Still to do | [`reads/RW-23-still-to-do.png`](reads/RW-23-still-to-do.png) | 390×844 | `RWUnfinished.dc.html` |
| RW-24 Photos | [`reads/RW-24-photos.png`](reads/RW-24-photos.png) | 390×844 | `RWPhotos.dc.html` |
| RW-25 Turn it in | [`reads/RW-25-turn-it-in.png`](reads/RW-25-turn-it-in.png) | 390×844 | `RWTurnIn.dc.html` |
| RW-26 Sending | [`reads/RW-26-sending.png`](reads/RW-26-sending.png) | 390×844 | `RWSending.dc.html` |
| RW-27 Turned in | [`reads/RW-27-turned-in.png`](reads/RW-27-turned-in.png) | 390×844 | `RWTurnedIn.dc.html` |
| RW-28 My reads | [`reads/RW-28-my-reads.png`](reads/RW-28-my-reads.png) | 390×844 | `RWHistory.dc.html` |
| RW-29 Reading settings | [`reads/RW-29-reading-settings.png`](reads/RW-29-reading-settings.png) | 390×844 | `RWSettings.dc.html` |
| FF-01 T Splash | [`tablet/FF-01-T-splash.png`](tablet/FF-01-T-splash.png) | 1024×768 | `TabSplash.dc.html` |
| FF-02 T Intro 1 | [`tablet/FF-02-T-intro-1.png`](tablet/FF-02-T-intro-1.png) | 1024×768 | `TabIntro1.dc.html` |
| FF-03 T Intro 2 | [`tablet/FF-03-T-intro-2.png`](tablet/FF-03-T-intro-2.png) | 1024×768 | `TabIntro2.dc.html` |
| FF-04 T Intro 3 | [`tablet/FF-04-T-intro-3.png`](tablet/FF-04-T-intro-3.png) | 1024×768 | `TabIntro3.dc.html` |
| FF-05 T Sign in | [`tablet/FF-05-T-sign-in.png`](tablet/FF-05-T-sign-in.png) | 1024×768 | `TabSignIn.dc.html` |
| FF-06 T Forgot password | [`tablet/FF-06-T-forgot-password.png`](tablet/FF-06-T-forgot-password.png) | 1024×768 | `TabForgot.dc.html` |
| FF-07 T Permissions | [`tablet/FF-07-T-permissions.png`](tablet/FF-07-T-permissions.png) | 1024×768 | `TabPermissions.dc.html` |
| FF-08 T First sync | [`tablet/FF-08-T-first-sync.png`](tablet/FF-08-T-first-sync.png) | 1024×768 | `TabFirstSync.dc.html` |
| FF-09 T The sidebar | [`tablet/FF-09-T-the-sidebar.png`](tablet/FF-09-T-the-sidebar.png) | 1024×768 | `TabDrawer.dc.html` |
| FF-10 T Today | [`tablet/FF-10-T-today.png`](tablet/FF-10-T-today.png) | 1024×768 | `TabToday.dc.html` |
| FF-11 T Nearby | [`tablet/FF-11-T-nearby.png`](tablet/FF-11-T-nearby.png) | 1024×768 | `TabNearby.dc.html` |
| FF-12 T Claim | [`tablet/FF-12-T-claim.png`](tablet/FF-12-T-claim.png) | 1024×768 | `TabClaim.dc.html` |
| FF-13 T Map | [`tablet/FF-13-T-map.png`](tablet/FF-13-T-map.png) | 1024×768 | `TabMap.dc.html` |
| FF-14 T The stop | [`tablet/FF-14-T-the-stop.png`](tablet/FF-14-T-the-stop.png) | 1024×768 | `TabStop.dc.html` |
| FF-15 T Job | [`tablet/FF-15-T-job.png`](tablet/FF-15-T-job.png) | 1024×768 | `TabJob.dc.html` |
| FF-16 T Safety | [`tablet/FF-16-T-safety.png`](tablet/FF-16-T-safety.png) | 1024×768 | `TabSafety.dc.html` |
| FF-17 T Tasks | [`tablet/FF-17-T-tasks.png`](tablet/FF-17-T-tasks.png) | 1024×768 | `TabTasks.dc.html` |
| FF-18 T Add a step | [`tablet/FF-18-T-add-a-step.png`](tablet/FF-18-T-add-a-step.png) | 1024×768 | `TabAddStep.dc.html` |
| FF-19 T Checklist | [`tablet/FF-19-T-checklist.png`](tablet/FF-19-T-checklist.png) | 1024×768 | `TabChecklist.dc.html` |
| FF-20 T Readings | [`tablet/FF-20-T-readings.png`](tablet/FF-20-T-readings.png) | 1024×768 | `TabReadings.dc.html` |
| FF-21 T Photos | [`tablet/FF-21-T-photos.png`](tablet/FF-21-T-photos.png) | 1024×768 | `TabPhotos.dc.html` |
| FF-22 T Before and after | [`tablet/FF-22-T-before-and-after.png`](tablet/FF-22-T-before-and-after.png) | 1024×768 | `TabCompare.dc.html` |
| FF-23 T Materials | [`tablet/FF-23-T-materials.png`](tablet/FF-23-T-materials.png) | 1024×768 | `TabMaterials.dc.html` |
| FF-24 T Parts used | [`tablet/FF-24-T-parts-used.png`](tablet/FF-24-T-parts-used.png) | 1024×768 | `TabParts.dc.html` |
| FF-25 T Customer | [`tablet/FF-25-T-customer.png`](tablet/FF-25-T-customer.png) | 1024×768 | `TabCustomer.dc.html` |
| FF-26 T Restoration | [`tablet/FF-26-T-restoration.png`](tablet/FF-26-T-restoration.png) | 1024×768 | `TabRestoration.dc.html` |
| FF-27 T Disconnect | [`tablet/FF-27-T-disconnect.png`](tablet/FF-27-T-disconnect.png) | 1024×768 | `TabDisconnect.dc.html` |
| FF-28 T Documents | [`tablet/FF-28-T-documents.png`](tablet/FF-28-T-documents.png) | 1024×768 | `TabDocuments.dc.html` |
| FF-29 T Crew | [`tablet/FF-29-T-crew.png`](tablet/FF-29-T-crew.png) | 1024×768 | `TabCrew.dc.html` |
| FF-30 T Notes | [`tablet/FF-30-T-notes.png`](tablet/FF-30-T-notes.png) | 1024×768 | `TabNotes.dc.html` |
| FF-31 T Activity | [`tablet/FF-31-T-activity.png`](tablet/FF-31-T-activity.png) | 1024×768 | `TabActivity.dc.html` |
| FF-32 T Debrief | [`tablet/FF-32-T-debrief.png`](tablet/FF-32-T-debrief.png) | 1024×768 | `TabDebrief.dc.html` |
| FF-33 T Signature | [`tablet/FF-33-T-signature.png`](tablet/FF-33-T-signature.png) | 1024×768 | `TabSignature.dc.html` |
| FF-34 T Close | [`tablet/FF-34-T-close.png`](tablet/FF-34-T-close.png) | 1024×768 | `TabClose.dc.html` |
| FF-35 T Completed | [`tablet/FF-35-T-completed.png`](tablet/FF-35-T-completed.png) | 1024×768 | `TabCompleted.dc.html` |
| FF-36 T Reopen | [`tablet/FF-36-T-reopen.png`](tablet/FF-36-T-reopen.png) | 1024×768 | `TabReopen.dc.html` |
| FF-37 T Raise an order | [`tablet/FF-37-T-raise-an-order.png`](tablet/FF-37-T-raise-an-order.png) | 1024×768 | `TabRaise.dc.html` |
| FF-38 T Scan | [`tablet/FF-38-T-scan.png`](tablet/FF-38-T-scan.png) | 1024×768 | `TabScan.dc.html` |
| FF-39 T Asset | [`tablet/FF-39-T-asset.png`](tablet/FF-39-T-asset.png) | 1024×768 | `TabAssets.dc.html` |
| FF-40 T Asset history | [`tablet/FF-40-T-asset-history.png`](tablet/FF-40-T-asset-history.png) | 1024×768 | `TabHistory.dc.html` |
| FF-41 T Asset search | [`tablet/FF-41-T-asset-search.png`](tablet/FF-41-T-asset-search.png) | 1024×768 | `TabSearch.dc.html` |
| FF-42 T Alerts | [`tablet/FF-42-T-alerts.png`](tablet/FF-42-T-alerts.png) | 1024×768 | `TabAlerts.dc.html` |
| FF-43 T Emergency | [`tablet/FF-43-T-emergency.png`](tablet/FF-43-T-emergency.png) | 1024×768 | `TabEmergency.dc.html` |
| FF-44 T Profile | [`tablet/FF-44-T-profile.png`](tablet/FF-44-T-profile.png) | 1024×768 | `TabProfile.dc.html` |
| FF-45 T Availability | [`tablet/FF-45-T-availability.png`](tablet/FF-45-T-availability.png) | 1024×768 | `TabAvailability.dc.html` |
| FF-46 T Shifts | [`tablet/FF-46-T-shifts.png`](tablet/FF-46-T-shifts.png) | 1024×768 | `TabShifts.dc.html` |
| FF-47 T Timesheet | [`tablet/FF-47-T-timesheet.png`](tablet/FF-47-T-timesheet.png) | 1024×768 | `TabTimesheet.dc.html` |
| FF-48 T Admin | [`tablet/FF-48-T-admin.png`](tablet/FF-48-T-admin.png) | 1024×768 | `TabAdmin.dc.html` |
| FF-49 T Van | [`tablet/FF-49-T-van.png`](tablet/FF-49-T-van.png) | 1024×768 | `TabVan.dc.html` |
| FF-50 T Sync | [`tablet/FF-50-T-sync.png`](tablet/FF-50-T-sync.png) | 1024×768 | `TabSync.dc.html` |
| FF-51 T Settings | [`tablet/FF-51-T-settings.png`](tablet/FF-51-T-settings.png) | 1024×768 | `TabSettings.dc.html` |
| FF-52 T Notifications | [`tablet/FF-52-T-notifications.png`](tablet/FF-52-T-notifications.png) | 1024×768 | `TabNotifications.dc.html` |
| FF-53 T Sign out | [`tablet/FF-53-T-sign-out.png`](tablet/FF-53-T-sign-out.png) | 1024×768 | `TabLogout.dc.html` |
| FF-54 T Dark | [`tablet/FF-54-T-dark.png`](tablet/FF-54-T-dark.png) | 1024×768 | `TabNight.dc.html` |
| FF-55 T Sunlight | [`tablet/FF-55-T-sunlight.png`](tablet/FF-55-T-sunlight.png) | 1024×768 | `TabSunlight.dc.html` |
| FF-56 Activate | [`phone/FF-56-activate.png`](phone/FF-56-activate.png) | 390×844 | `Activate.dc.html` |
| FF-57 Your password | [`phone/FF-57-your-password.png`](phone/FF-57-your-password.png) | 390×844 | `SetPassword.dc.html` |
| FF-58 Hand it back | [`phone/FF-58-hand-it-back.png`](phone/FF-58-hand-it-back.png) | 390×844 | `Reject.dc.html` |
| FF-59 Add a reading | [`phone/FF-59-add-a-reading.png`](phone/FF-59-add-a-reading.png) | 390×844 | `AddReading.dc.html` |
| FF-60 Asset papers | [`phone/FF-60-asset-papers.png`](phone/FF-60-asset-papers.png) | 390×844 | `AssetDocs.dc.html` |
| FF-61 Reconnect | [`phone/FF-61-reconnect.png`](phone/FF-61-reconnect.png) | 390×844 | `Reconnect.dc.html` |
| FF-62 Pick a template | [`phone/FF-62-pick-a-template.png`](phone/FF-62-pick-a-template.png) | 390×844 | `PickTemplate.dc.html` |
| FF-56 T Activate | [`tablet/FF-56-T-activate.png`](tablet/FF-56-T-activate.png) | 1024×768 | `TabActivate.dc.html` |
| FF-57 T Your password | [`tablet/FF-57-T-your-password.png`](tablet/FF-57-T-your-password.png) | 1024×768 | `TabSetPassword.dc.html` |
| FF-58 T Hand it back | [`tablet/FF-58-T-hand-it-back.png`](tablet/FF-58-T-hand-it-back.png) | 1024×768 | `TabReject.dc.html` |
| FF-59 T Add a reading | [`tablet/FF-59-T-add-a-reading.png`](tablet/FF-59-T-add-a-reading.png) | 1024×768 | `TabAddReading.dc.html` |
| FF-60 T Asset papers | [`tablet/FF-60-T-asset-papers.png`](tablet/FF-60-T-asset-papers.png) | 1024×768 | `TabAssetDocs.dc.html` |
| FF-61 T Reconnect | [`tablet/FF-61-T-reconnect.png`](tablet/FF-61-T-reconnect.png) | 1024×768 | `TabReconnect.dc.html` |
| FF-62 T Pick a template | [`tablet/FF-62-T-pick-a-template.png`](tablet/FF-62-T-pick-a-template.png) | 1024×768 | `TabPickTemplate.dc.html` |
| FF-63 Home | [`phone/FF-63-home.png`](phone/FF-63-home.png) | 390×844 | `Home.dc.html` |
| FF-63 T Home | [`tablet/FF-63-T-home.png`](tablet/FF-63-T-home.png) | 1024×768 | `TabHome.dc.html` |
| RW-01 T My routes | [`tablet/RW-01-T-my-routes.png`](tablet/RW-01-T-my-routes.png) | 1024×768 | `TabRWRoutes.dc.html` |
| RW-02 T Route summary | [`tablet/RW-02-T-route-summary.png`](tablet/RW-02-T-route-summary.png) | 1024×768 | `TabRWSummary.dc.html` |
| RW-03 T Download | [`tablet/RW-03-T-download.png`](tablet/RW-03-T-download.png) | 1024×768 | `TabRWDownload.dc.html` |
| RW-04 T Route map | [`tablet/RW-04-T-route-map.png`](tablet/RW-04-T-route-map.png) | 1024×768 | `TabRWMap.dc.html` |
| RW-05 T The walk | [`tablet/RW-05-T-the-walk.png`](tablet/RW-05-T-the-walk.png) | 1024×768 | `TabRWWalk.dc.html` |
| RW-06 T The stop | [`tablet/RW-06-T-the-stop.png`](tablet/RW-06-T-the-stop.png) | 1024×768 | `TabRWStop.dc.html` |
| RW-07 T Getting in | [`tablet/RW-07-T-getting-in.png`](tablet/RW-07-T-getting-in.png) | 1024×768 | `TabRWAccess.dc.html` |
| RW-08 T Find a meter | [`tablet/RW-08-T-find-a-meter.png`](tablet/RW-08-T-find-a-meter.png) | 1024×768 | `TabRWFind.dc.html` |
| RW-09 T Read entry | [`tablet/RW-09-T-read-entry.png`](tablet/RW-09-T-read-entry.png) | 1024×768 | `TabRWRead.dc.html` |
| RW-10 T Dials | [`tablet/RW-10-T-dials.png`](tablet/RW-10-T-dials.png) | 1024×768 | `TabRWDials.dc.html` |
| RW-11 T Scan to confirm | [`tablet/RW-11-T-scan-to-confirm.png`](tablet/RW-11-T-scan-to-confirm.png) | 1024×768 | `TabRWScan.dc.html` |
| RW-12 T Master and subs | [`tablet/RW-12-T-master-and-subs.png`](tablet/RW-12-T-master-and-subs.png) | 1024×768 | `TabRWSubmeters.dc.html` |
| RW-13 T The reading | [`tablet/RW-13-T-the-reading.png`](tablet/RW-13-T-the-reading.png) | 1024×768 | `TabRWRecord.dc.html` |
| RW-14 T The camera | [`tablet/RW-14-T-the-camera.png`](tablet/RW-14-T-the-camera.png) | 1024×768 | `TabRWCamera.dc.html` |
| RW-15 T High or low | [`tablet/RW-15-T-high-or-low.png`](tablet/RW-15-T-high-or-low.png) | 1024×768 | `TabRWChallenge.dc.html` |
| RW-16 T Second look | [`tablet/RW-16-T-second-look.png`](tablet/RW-16-T-second-look.png) | 1024×768 | `TabRWReread.dc.html` |
| RW-17 T Can't read | [`tablet/RW-17-T-can-t-read.png`](tablet/RW-17-T-can-t-read.png) | 1024×768 | `TabRWCantRead.dc.html` |
| RW-18 T Different meter | [`tablet/RW-18-T-different-meter.png`](tablet/RW-18-T-different-meter.png) | 1024×768 | `TabRWWrongMeter.dc.html` |
| RW-19 T Not on the route | [`tablet/RW-19-T-not-on-the-route.png`](tablet/RW-19-T-not-on-the-route.png) | 1024×768 | `TabRWScanOff.dc.html` |
| RW-20 T Add a meter | [`tablet/RW-20-T-add-a-meter.png`](tablet/RW-20-T-add-a-meter.png) | 1024×768 | `TabRWAddMeter.dc.html` |
| RW-21 T Raise it | [`tablet/RW-21-T-raise-it.png`](tablet/RW-21-T-raise-it.png) | 1024×768 | `TabRWRaise.dc.html` |
| RW-22 T Where you are | [`tablet/RW-22-T-where-you-are.png`](tablet/RW-22-T-where-you-are.png) | 1024×768 | `TabRWProgress.dc.html` |
| RW-23 T Still to do | [`tablet/RW-23-T-still-to-do.png`](tablet/RW-23-T-still-to-do.png) | 1024×768 | `TabRWUnfinished.dc.html` |
| RW-24 T Photos | [`tablet/RW-24-T-photos.png`](tablet/RW-24-T-photos.png) | 1024×768 | `TabRWPhotos.dc.html` |
| RW-25 T Turn it in | [`tablet/RW-25-T-turn-it-in.png`](tablet/RW-25-T-turn-it-in.png) | 1024×768 | `TabRWTurnIn.dc.html` |
| RW-26 T Sending | [`tablet/RW-26-T-sending.png`](tablet/RW-26-T-sending.png) | 1024×768 | `TabRWSending.dc.html` |
| RW-27 T Turned in | [`tablet/RW-27-T-turned-in.png`](tablet/RW-27-T-turned-in.png) | 1024×768 | `TabRWTurnedIn.dc.html` |
| RW-28 T My reads | [`tablet/RW-28-T-my-reads.png`](tablet/RW-28-T-my-reads.png) | 1024×768 | `TabRWHistory.dc.html` |
| RW-29 T Reading settings | [`tablet/RW-29-T-reading-settings.png`](tablet/RW-29-T-reading-settings.png) | 1024×768 | `TabRWSettings.dc.html` |
| Switch.dc.html | [`phone/Switch.png`](phone/Switch.png) | 390×844 | `Switch.dc.html` |
