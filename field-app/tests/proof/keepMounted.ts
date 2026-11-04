/**
 * Imported FIRST by a sweep that mounts the app once and opens screen after
 * screen in it, one test per screen: Testing Library's automatic cleanup would
 * otherwise unmount the app after the first test. The sweep unmounts it itself.
 */
process.env.RNTL_SKIP_AUTO_CLEANUP = 'true';

export {};
