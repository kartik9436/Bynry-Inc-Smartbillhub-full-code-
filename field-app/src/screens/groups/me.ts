/** Screens built by the "me" wave. Each wave owns its own file so waves never edit the same lines. */
import { type ComponentType, createElement } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { listBesideDetail, withTabletLayout } from '../../tablet/layoutSlot';
import { AlertDetail, AlertsList } from '../../tablet/layouts/AlertsLayout';
import {
  AdminList,
  AdminTaskDetail,
  AvailabilityDetail,
  AvailabilityList,
  ProfileDetail,
  ProfileList,
  ShiftDayDetail,
  ShiftsList,
  TimesheetDay,
  TimesheetDays,
  VanItemDetail,
  VanList,
} from '../../tablet/layouts/MeLayout';
import {
  NotifyDetail,
  NotifyKinds,
  SettingsDetail,
  SettingsSections,
  SyncDetail,
  SyncDirections,
} from '../../tablet/layouts/SettingsLayout';
import { AdminTasksScreen } from '../me/AdminTasksScreen';
import { AlertsScreen } from '../me/AlertsScreen';
import { AvailabilityScreen } from '../me/AvailabilityScreen';
import { EmergencyScreen } from '../me/EmergencyScreen';
import { NotificationsScreen } from '../me/NotificationsScreen';
import { ProfileScreen } from '../me/ProfileScreen';
import { SettingsScreen } from '../me/SettingsScreen';
import { ShiftsScreen } from '../me/ShiftsScreen';
import { SignOutScreen } from '../me/SignOutScreen';
import { SwitchScreen } from '../me/SwitchScreen';
import { SyncScreen } from '../me/SyncScreen';
import { DarkThemeScreen, SunlightThemeScreen } from '../me/ThemeProofScreen';
import { TimesheetScreen } from '../me/TimesheetScreen';
import { VanScreen } from '../me/VanScreen';

/** A fresh component, so marking it never marks the phone screen the list pane mounts. */
function AlertsPhone() {
  return createElement(AlertsScreen);
}

export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  // T-28: FF-42 T *Alerts beside the one you opened*.
  'FF-42': withTabletLayout(AlertsPhone, { frame: 'T2', list: AlertsList, detail: AlertDetail }),
  // T-29: FF-43 T draws the same pair as FF-42 T — the alerts beside the emergency.
  'FF-43': listBesideDetail(EmergencyScreen, AlertsList, AlertDetail),
  'FF-44': listBesideDetail(ProfileScreen, ProfileList, ProfileDetail),
  'FF-45': listBesideDetail(AvailabilityScreen, AvailabilityList, AvailabilityDetail),
  'FF-46': listBesideDetail(ShiftsScreen, ShiftsList, ShiftDayDetail),
  'FF-47': listBesideDetail(TimesheetScreen, TimesheetDays, TimesheetDay),
  'FF-48': listBesideDetail(AdminTasksScreen, AdminList, AdminTaskDetail),
  'FF-49': listBesideDetail(VanScreen, VanList, VanItemDetail),
  'FF-50': listBesideDetail(SyncScreen, SyncDirections, SyncDetail),
  'FF-51': listBesideDetail(SettingsScreen, SettingsSections, SettingsDetail),
  'FF-52': listBesideDetail(NotificationsScreen, NotifyKinds, NotifyDetail),
  'FF-53': SignOutScreen,
  'FF-54': DarkThemeScreen,
  'FF-55': SunlightThemeScreen,
  SWITCH: SwitchScreen,
};
