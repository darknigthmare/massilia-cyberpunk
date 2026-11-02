'use strict';

// Evidence covers the installed extension, its inherited inputs and the exact
// generated pages exercised by QA. All hashes are taken from disk before/after.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../../..');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const parentScripts = Object.freeze({
  'game/tests/v74/browser_smoke.cjs': '4f167c3c7722b484369f8e9e4345498fcc74c4a385b073aaa85c430c11844248',
  'game/tests/v74/browser_features.cjs': '6881cf87ec5e3aafa72590128804d4c3902fec76431f392269f27f785080318e',
  'game/tests/v74/browser_mechanics.cjs': '74860cc9ecb974f225eab9034f08a0e9524a356d86572ee55adf9f47608d860c',
  'game/tests/v74/continuity_browser.cjs': 'ed2a9dfad586fc252b6023c9a9af5a14c71a5077fcadaa875a5a465ba45268cb',
});
const parentPages = Object.freeze({
  'game/SOMA_MASSILIA_URBAIN_v0_74.html': '1b776a1b8b3c2861093e1670d1b203025b158bd0fb0f464f0ab3d58086139330',
  'game/metropole-viewer-v74.html': '69d6713e08f9f8deaf1f294c0e3ffb846d930e4b2a4e8d7cbe714d8058a1c7bd',
});
async function filesBelow(relative) {
  let entries;
  try { entries = await fs.readdir(path.join(root, relative), { withFileTypes: true }); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  const result = [];
  for (const entry of entries) {
    const filename = path.posix.join(relative, entry.name);
    if (entry.isDirectory() && entry.name !== '__pycache__') result.push(...await filesBelow(filename));
    else if (entry.isFile() && /\.(?:js|cjs|py|json)$/.test(entry.name)) result.push(filename);
  }
  return result;
}
function validateEvidence(sources, frozen = { ...parentScripts, ...parentPages }) {
  for (const [filename, expected] of Object.entries(frozen)) {
    if (sources[filename] !== expected) throw Error('Frozen QA input changed or missing: ' + filename);
  }
  for (const filename of ['game/SOMA_MASSILIA_URBAIN_v0_75.html', 'game/metropole-viewer-v75.html']) {
    if (!/^[a-f0-9]{64}$/.test(sources[filename] || '')) throw Error('Built QA page missing: ' + filename);
  }
}
function validateBuildEvidence(report, sources, html) {
  if (report.version !== '0.75.0' || report.sha256 !== sources[html]) throw Error('Built QA page and build report diverge: ' + html);
  if (!report.inputs?.sources75 || Object.keys(report.inputs.sources75).length < 1) throw Error('Built QA page has no source input evidence: ' + html);
  for (const [relative, expected] of Object.entries(report.inputs.sources75)) {
    if (sources['game/' + relative] !== expected.sha256) throw Error('Built QA page uses stale source input: ' + relative);
  }
}
async function sourceEvidence(script) {
  const filenames = new Set([
    'game/SOMA_MASSILIA_URBAIN_v0_75.html', 'game/metropole-viewer-v75.html',
    'game/build_v75.py', 'game/tools/build_metropole_viewer_v75.py',
    'game/tools/launch_cache_v75.py', 'game/tools/serve_v75.py', 'lancer.py',
    'game/data/v75/terrain-source.json',
    'game/data/v75/BUILD_REPORT.json', 'game/data/v75/VIEWER_BUILD_REPORT.json',
    ...Object.keys(parentScripts), ...Object.keys(parentPages),
    ...await filesBelow('game/src/v75'), ...await filesBelow('game/src/v74'),
    path.relative(root, script), 'game/tests/v75/browser_provenance.cjs',
  ]);
  // Historical pages produce the authentic exports consumed by continuity75.
  for (const edition of [70, 71, 73]) filenames.add(`game/SOMA_MASSILIA_URBAIN_v0_${edition}.html`);
  for (const name of await fs.readdir(path.join(root, 'game/tools'))) {
    if (/^v75_.*\.py$/.test(name)) filenames.add('game/tools/' + name);
  }
  const sources = {};
  for (const filename of [...filenames].sort()) {
    try { sources[filename] = hash(await fs.readFile(path.join(root, filename))); }
    catch (error) { if (error.code === 'ENOENT') sources[filename] = null; else throw error; }
  }
  validateEvidence(sources);
  for (const [relative, html] of [['BUILD_REPORT.json', 'game/SOMA_MASSILIA_URBAIN_v0_75.html'], ['VIEWER_BUILD_REPORT.json', 'game/metropole-viewer-v75.html']]) {
    const report = JSON.parse(await fs.readFile(path.join(root, 'game/data/v75', relative), 'utf8'));
    validateBuildEvidence(report, sources, html);
  }
  return {
    recordedAt: new Date().toISOString(),
    gitHEAD: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    branch: execFileSync('git', ['branch', '--show-current'], { cwd: root, encoding: 'utf8' }).trim(),
    script: path.relative(root, script), sources, aggregateSHA256: hash(JSON.stringify(sources)),
    sourceScope: 'Current v75 runtime and generation, inherited v74 runtime and generated pages, authentic export pages70/71/73, executing QA script and helper; parent74 hashes are pinned to its frozen PASS report.',
  };
}
async function finishEvidence(report, script) {
  try {
    report.provenanceFinished = await sourceEvidence(script);
    report.sourceSetUnchanged = report.provenance?.aggregateSHA256 === report.provenanceFinished.aggregateSHA256;
    if (!report.sourceSetUnchanged) throw Error('Tested source set changed during browser execution.');
  } catch (error) {
    report.passed = false;
    report.sourceSetUnchanged = false;
    report.provenanceFailure = String(error.stack || error);
    process.exitCode = 1;
  }
}
module.exports = { sourceEvidence, finishEvidence, validateEvidence, validateBuildEvidence, parentScripts, parentPages };
