/**
 * `shared/tokens.ts` sits outside both apps, with no `node_modules` beside it,
 * so it must compile to code that requires NOTHING: a Babel runtime helper
 * (emitted for an array spread, a destructure, a for-of) cannot be resolved
 * from `shared/` and breaks every importer. This compiles the file with the
 * app's own preset, as Metro and jest-expo do, and fails on any `require(`.
 */
import { transformFileSync } from '@babel/core';
import { resolve } from 'path';

test('shared/tokens.ts compiles with no require()', () => {
  const file = resolve(__dirname, '../../../shared/tokens.ts');
  const out = transformFileSync(file, {
    presets: ['babel-preset-expo'],
    caller: { name: 'metro', platform: 'ios' } as never,
    babelrc: false,
    configFile: false,
  });
  const code = out?.code ?? '';
  expect(code.length).toBeGreaterThan(1000);
  expect(code).not.toMatch(/require\(/);
});
