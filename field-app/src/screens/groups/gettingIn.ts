/** Screens built by the "gettingIn" wave. Each wave owns its own file so waves never edit the same lines.
 *  T-15 Getting in: FF-01 Splash, FF-02/03/04 Intro, FF-05 Sign in, FF-06 Forgot password, FF-07 Permissions,
 *  FF-08 First sync, FF-56 Activate, FF-57 Your password. FF-09 is the menu (the drawer itself, `navigation/MenuContent.tsx`). */
import { type ComponentType } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { ActivateScreen } from '../gettingIn/ActivateScreen';
import { FirstSyncScreen } from '../gettingIn/FirstSyncScreen';
import { ForgotPasswordScreen } from '../gettingIn/ForgotPasswordScreen';
import { IntroOneScreen, IntroThreeScreen, IntroTwoScreen } from '../gettingIn/IntroScreen';
import { PermissionsScreen } from '../gettingIn/PermissionsScreen';
import { SignInScreen } from '../gettingIn/SignInScreen';
import { SplashScreen } from '../gettingIn/SplashScreen';
import { YourPasswordScreen } from '../gettingIn/YourPasswordScreen';

export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  'FF-01': SplashScreen,
  'FF-02': IntroOneScreen,
  'FF-03': IntroTwoScreen,
  'FF-04': IntroThreeScreen,
  'FF-05': SignInScreen,
  'FF-06': ForgotPasswordScreen,
  'FF-07': PermissionsScreen,
  'FF-08': FirstSyncScreen,
  'FF-56': ActivateScreen,
  'FF-57': YourPasswordScreen,
};
