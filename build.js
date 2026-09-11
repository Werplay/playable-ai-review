#!/usr/bin/env node
/**
 * Build entry (also used by build-all.sh, one process per ad network).
 *
 *   node build.js [--network <name>]
 *
 * Adds `target: ['web','es5']` on top of playable-scripts' own config: the default
 * build emits an arrow-function webpack runtime, and Mintegral rejects bundles that
 * are not ES5. Everything else comes from playable-scripts as-is.
 */
process.env.BABEL_ENV = 'production';
process.env.NODE_ENV = 'production';

const { runBuild } = require('@smoud/playable-scripts');

const i = process.argv.indexOf('--network');
const network = i > -1 ? process.argv[i + 1] : undefined;

runBuild(undefined, network ? { network } : undefined, undefined, {
  target: ['web', 'es5']
}).catch(() => process.exit(1));
