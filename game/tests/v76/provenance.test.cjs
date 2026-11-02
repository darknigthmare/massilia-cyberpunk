'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateEvidence, validateBuildEvidence, producerFiles, parentScripts, parentPages, currentPages } = require('./browser_provenance.cjs');
const complete = () => ({ ...parentScripts, ...parentPages, ...Object.fromEntries(currentPages.map((filename, i) => [filename, String(i + 1).repeat(64)])) });
function fixture(html = currentPages[0]) {
  const fingerprint = { bytes: 12, sha256: 'a'.repeat(64) };
  const inputs = { modules76: ['entry-runtime'], sources76: { 'build_v76.py': fingerprint, 'src/v76/entry-runtime.js': fingerprint }, parentInputs: { sources75: { 'tools/v75_terrain.py': fingerprint } } };
  const sources = { ...complete(), ...Object.fromEntries(Object.entries(producerFiles(inputs)).map(([name, value]) => [name, value.sha256])) };
  return { html, inputs, sources, report: { version: '0.76.0', output: html.split('/').at(-1), sha256: sources[html], inputs: structuredClone(inputs) } };
}
test('exact frozen75 QA and all real historical export pages permit current qualification', () => validateEvidence(complete()));
test('all seven frozen75 suite scripts and their helper are individually protected', () => {
  for (const filename of Object.keys(parentScripts)) { const sources = complete(); sources[filename] = 'e'.repeat(64); assert.throws(() => validateEvidence(sources), /Frozen QA input changed/); }
});
test('historical pages including actual75 cannot be silently relabelled or regenerated', () => {
  for (const filename of Object.keys(parentPages)) { const sources = complete(); delete sources[filename]; assert.throws(() => validateEvidence(sources), /Frozen QA input changed/); }
});
test('both current campaign and viewer are required independently', () => {
  for (const filename of currentPages) { const sources = complete(); delete sources[filename]; assert.throws(() => validateEvidence(sources), /Built QA page missing/); }
});
test('both pages bind their actual bytes, output identity and producing inventory', () => {
  for (const html of currentPages) { const f = fixture(html); assert.doesNotThrow(() => validateBuildEvidence(f.report, f.sources, html, f.inputs)); f.report.sha256 = 'f'.repeat(64); assert.throws(() => validateBuildEvidence(f.report, f.sources, html, f.inputs), /page and build report diverge/); }
});
test('a viewer report cannot qualify the campaign merely by using its hash', () => {
  const f = fixture(); f.report.output = 'metropole-viewer-v76.html'; assert.throws(() => validateBuildEvidence(f.report, f.sources, f.html, f.inputs), /page and build report diverge/);
});
test('stable stale HTML fails after a current runtime or producer edit', () => {
  for (const filename of ['game/build_v76.py', 'game/src/v76/entry-runtime.js', 'game/tools/v75_terrain.py']) { const f = fixture(); f.sources[filename] = 'b'.repeat(64); assert.throws(() => validateBuildEvidence(f.report, f.sources, f.html, f.inputs), /stale producer input/); }
});
test('report omissions cannot hide an actual newly used producer', () => {
  const f = fixture(); f.inputs.sources76['tools/v76_mobility.py'] = { bytes: 4, sha256: 'd'.repeat(64) }; f.sources['game/tools/v76_mobility.py'] = 'd'.repeat(64);
  assert.throws(() => validateBuildEvidence(f.report, f.sources, f.html, f.inputs), /actual producing inputs/);
});
test('module inventory must identify every declared current module exactly once', () => {
  for (const names of [[], ['entry-runtime', 'entry-runtime'], ['missing-runtime']]) { const f = fixture(); f.report.inputs.modules76 = names; assert.throws(() => validateBuildEvidence(f.report, f.sources, f.html, f.inputs), /incomplete module evidence/); }
});
test('missing actual inventory and conflicting inherited fingerprints fail closed', () => {
  const f = fixture(); assert.throws(() => validateBuildEvidence(f.report, f.sources, f.html), /actual producing inputs/);
  f.inputs.parentInputs.sources75['build_v76.py'] = { bytes: 1, sha256: 'f'.repeat(64) };
  assert.throws(() => producerFiles(f.inputs), /Conflicting producer evidence/);
});
