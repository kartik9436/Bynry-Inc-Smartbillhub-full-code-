/** Types for `withFontScaleConfigChanges.js` (DEF-FLD-10589) — the docstring is there. */
import type { ConfigPlugin } from 'expo/config-plugins';

declare const withFontScaleConfigChanges: ConfigPlugin & {
  default: ConfigPlugin;
  REQUIRED_CONFIG_CHANGES: readonly string[];
  mergeConfigChanges(current: string | undefined): string;
  addFontScaleConfigChanges<M extends { manifest: unknown }>(androidManifest: M): M;
  addConfigurationListener(contents: string, language: string): string;
};
export = withFontScaleConfigChanges;
