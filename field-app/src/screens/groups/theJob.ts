/**
 * Screens built by the "theJob" wave — T-18 Opening a job, T-19 Doing the
 * work, and FF-58…FF-60. Each wave owns its own file so waves never edit the
 * same lines. The screens live in `../theJob/`; `jobScreen` puts the theme and
 * the crash boundary around each one.
 */
import { type ComponentType } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { withTabletLayout } from '../../tablet/layoutSlot';
import { JobContext, JobTasks } from '../../tablet/layouts/JobLayout';
import { AddReading } from '../theJob/AddReading';
import { AddStep } from '../theJob/AddStep';
import { AssetPapers } from '../theJob/AssetPapers';
import { Checklist } from '../theJob/Checklist';
import { Compare } from '../theJob/Compare';
import { HandBack } from '../theJob/HandBack';
import { JobOverview } from '../theJob/JobOverview';
import { jobScreen } from '../theJob/JobScreen';
import { Materials } from '../theJob/Materials';
import { PartsUsed } from '../theJob/PartsUsed';
import { Photos } from '../theJob/Photos';
import { Readings } from '../theJob/Readings';
import { Safety } from '../theJob/Safety';
import { Tasks } from '../theJob/Tasks';

/** T-28 on a tablet: FF-15 *the job with its tasks beside it* (T3, its own
 *  context), FF-20 *readings in two columns* and FF-21 *the photo wall* (T4 —
 *  the screens lay their own grid out by `fitColumns`, so the wide pane IS the
 *  screen). */
const readings = jobScreen('FF-20', Readings);
const photos = jobScreen('FF-21', Photos);

export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  'FF-15': withTabletLayout(jobScreen('FF-15', JobOverview), { frame: 'T3', context: JobContext, content: JobTasks }),
  'FF-16': jobScreen('FF-16', Safety),
  'FF-17': jobScreen('FF-17', Tasks),
  'FF-18': jobScreen('FF-18', AddStep),
  'FF-19': jobScreen('FF-19', Checklist),
  'FF-20': withTabletLayout(readings, { frame: 'T4', pane: readings }),
  'FF-21': withTabletLayout(photos, { frame: 'T4', pane: photos }),
  'FF-22': jobScreen('FF-22', Compare),
  'FF-23': jobScreen('FF-23', Materials),
  'FF-24': jobScreen('FF-24', PartsUsed),
  'FF-58': jobScreen('FF-58', HandBack),
  'FF-59': jobScreen('FF-59', AddReading),
  'FF-60': jobScreen('FF-60', AssetPapers),
};
