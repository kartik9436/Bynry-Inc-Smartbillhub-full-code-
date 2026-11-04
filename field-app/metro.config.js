// Metro for the field app (Expo SDK 53).
//
// The app reads two things from outside its own folder, and Metro will only
// bundle files under its project root or a watch folder:
//  - ../07-frontend/src/i18n/locales — the eleven shared catalogues; the field
//    app takes their `field.*` keys (decision log 2026-10-21, conflict #3).
//  - ../shared — the token module both apps read (T-06), once it exists.
// A folder that does not exist yet is left out rather than crashing the
// bundler, so the app builds before and after `shared/` lands.
const fs = require('fs');
const path = require('path');
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

const extra = [
  path.resolve(__dirname, '../07-frontend/src/i18n/locales'),
  path.resolve(__dirname, '../shared'),
].filter((dir) => fs.existsSync(dir));

config.watchFolders = [...(config.watchFolders ?? []), ...extra];

module.exports = config;
