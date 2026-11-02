'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateEvidence, validateBuildEvidence, parentScripts, parentPages } = require('./browser_provenance.cjs');
const complete = () => ({ ...parentScripts, ...parentPages,
  'game/SOMA_MASSILIA_URBAIN_v0_75.html': 'a'.repeat(64),
  'game/metropole-viewer-v75.html': 'b'.repeat(64) });

test('QA evidence accepts exact frozen parents and both current built pages', () => {
  assert.doesNotThrow(() => validateEvidence(complete()));
});
test('an altered frozen QA parent invalidates browser qualification', () => {
  const sources = complete();
  sources['game/tests/v74/browser_smoke.cjs'] = 'c'.repeat(64);
  assert.throws(() => validateEvidence(sources), /Frozen QA input changed.*browser_smoke/);
});
test('an altered generated parent74 cannot be qualified by copying new source hashes', () => {
  const sources = complete();
  sources['game/SOMA_MASSILIA_URBAIN_v0_74.html'] = 'c'.repeat(64);
  assert.throws(() => validateEvidence(sources), /Frozen QA input changed.*v0_74/);
});
test('missing built campaign or viewer75 prevents a false browser PASS', () => {
  for (const filename of ['game/SOMA_MASSILIA_URBAIN_v0_75.html', 'game/metropole-viewer-v75.html']) {
    const sources = complete(); delete sources[filename];
    assert.throws(() => validateEvidence(sources), /Built QA page missing/);
  }
});
test('a stable stale HTML cannot qualify newly edited sources75', () => {
  const html = 'game/SOMA_MASSILIA_URBAIN_v0_75.html';
  const sources = { ...complete(), 'game/src/v75/combat-telegraph-runtime.js': 'd'.repeat(64) };
  const report = { version: '0.75.0', sha256: sources[html], inputs: { sources75: {
    'src/v75/combat-telegraph-runtime.js': { sha256: 'c'.repeat(64) } } } };
  assert.throws(() => validateBuildEvidence(report, sources, html), /stale source input/);
  report.inputs.sources75['src/v75/combat-telegraph-runtime.js'].sha256 = 'd'.repeat(64);
  assert.doesNotThrow(() => validateBuildEvidence(report, sources, html));
  report.sha256 = 'e'.repeat(64);
  assert.throws(() => validateBuildEvidence(report, sources, html), /page and build report diverge/);
});
