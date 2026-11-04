/** Screens built by the "onSite" wave. Each wave owns its own file so waves never edit the same lines. */
import { type ComponentType } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { listBesideDetail } from '../../tablet/layoutSlot';
import { ActivityDay, ActivityDays, CrewDetail, CrewList, DocumentDetail, DocumentsList } from '../../tablet/layouts/OnSiteLayout';
import { ActivityScreen } from '../onSite/ActivityScreen';
import { waveScreen } from '../onSite/common';
import { CrewScreen } from '../onSite/CrewScreen';
import { CustomerScreen } from '../onSite/CustomerScreen';
import { DisconnectScreen } from '../onSite/DisconnectScreen';
import { DocumentsScreen } from '../onSite/DocumentsScreen';
import { NotesScreen } from '../onSite/NotesScreen';
import { ReconnectScreen } from '../onSite/ReconnectScreen';
import { RestorationScreen } from '../onSite/RestorationScreen';

export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  'FF-25': waveScreen('FF-25', CustomerScreen),
  'FF-26': waveScreen('FF-26', RestorationScreen),
  'FF-27': waveScreen('FF-27', DisconnectScreen),
  'FF-28': listBesideDetail(waveScreen('FF-28', DocumentsScreen), DocumentsList, DocumentDetail),
  'FF-29': listBesideDetail(waveScreen('FF-29', CrewScreen), CrewList, CrewDetail),
  'FF-30': waveScreen('FF-30', NotesScreen),
  'FF-31': listBesideDetail(waveScreen('FF-31', ActivityScreen), ActivityDays, ActivityDay),
  'FF-61': waveScreen('FF-61', ReconnectScreen),
};
