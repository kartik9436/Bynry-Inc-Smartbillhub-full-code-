/**
 * Phone or tablet, and how wide the window is — ONE decision for the whole
 * app. The test itself is the shell's (`navigation/layout.ts`, the short side
 * ≥ 600) and is not restated here; this only carries its answer down the tree
 * so a frame, a pane and a screen all read the same one.
 *
 * `AppNavigator` mounts the provider with the answer it already computed
 * (including its `tablet` override for tests and previews), so the sidebar and
 * the frames can never disagree about which device they are on. Outside a
 * provider the hook answers from the window, by the same test.
 */
import { createContext, type ReactNode, useContext, useMemo } from 'react';
import { useWindowDimensions } from 'react-native';

import { isTabletSize } from '../navigation/layout';

export interface FormFactor {
  tablet: boolean;
  width: number;
  height: number;
  orientation: 'landscape' | 'portrait';
}

const FormFactorContext = createContext<FormFactor | null>(null);

function describe(tablet: boolean, width: number, height: number): FormFactor {
  return { tablet, width, height, orientation: width >= height ? 'landscape' : 'portrait' };
}

export function FormFactorProvider(props: {
  children: ReactNode;
  /** The shell's answer. Omitted → the shell's test on the window. */
  tablet?: boolean;
  /** Override the window (tests, previews). */
  window?: { width: number; height: number };
}) {
  const live = useWindowDimensions();
  const width = props.window?.width ?? live.width;
  const height = props.window?.height ?? live.height;
  const tablet = props.tablet ?? isTabletSize(width, height);
  const value = useMemo(() => describe(tablet, width, height), [tablet, width, height]);
  return <FormFactorContext.Provider value={value}>{props.children}</FormFactorContext.Provider>;
}

export function useFormFactor(): FormFactor {
  const provided = useContext(FormFactorContext);
  const live = useWindowDimensions();
  return provided ?? describe(isTabletSize(live.width, live.height), live.width, live.height);
}
