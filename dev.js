#!/usr/bin/env node
/**
 * Dev entry. Mirrors build.js so a missing named import fails here too, instead of
 * printing a warning and silently resolving to `undefined` at runtime.
 */
process.env.BABEL_ENV = 'development';
process.env.NODE_ENV = 'development';

const { runDev } = require('@smoud/playable-scripts');

runDev(undefined, undefined, undefined, {
  module: { parser: { javascript: { exportsPresence: 'error' } } }
});
