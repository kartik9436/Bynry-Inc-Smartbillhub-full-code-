/**
 * Which component each screen id mounts. Today every one is the placeholder;
 * a lane that builds a screen replaces ITS entry here and nothing else, so the
 * route name, the doors pointing at it and the doors test all stay as they
 * are.
 */
import { type ComponentType } from 'react';

import { SCREEN_IDS, type ScreenId } from '../navigation/screens';
import { PlaceholderScreen } from './PlaceholderScreen';
import { SCREENS as closing } from './groups/closing';
import { SCREENS as gettingIn } from './groups/gettingIn';
import { SCREENS as me } from './groups/me';
import { SCREENS as onSite } from './groups/onSite';
import { SCREENS as raise } from './groups/raise';
import { SCREENS as reads } from './groups/reads';
import { SCREENS as theDay } from './groups/theDay';
import { SCREENS as theJob } from './groups/theJob';

/** Built screens, one file per wave; anything not built yet stays the placeholder. */
const BUILT: Partial<Record<ScreenId, ComponentType>> = {
  ...gettingIn,
  ...theDay,
  ...theJob,
  ...onSite,
  ...closing,
  ...raise,
  ...me,
  ...reads,
};

function placeholderFor(id: ScreenId): ComponentType {
  function Placeholder() {
    return <PlaceholderScreen id={id} />;
  }
  Placeholder.displayName = `Placeholder(${id})`;
  return Placeholder;
}

export const SCREEN_COMPONENTS: Readonly<Record<ScreenId, ComponentType>> = Object.fromEntries(
  SCREEN_IDS.map((id) => [id, BUILT[id] ?? placeholderFor(id)]),
) as Record<ScreenId, ComponentType>;
