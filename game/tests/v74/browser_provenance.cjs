'use strict';

// Evidence identifies the local files actually tested, including generated HTML.
// A commit alone is insufficient while the shared worktree is being assembled.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../../..');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const parentScripts = {
  'game/tests/v73/browser_smoke.cjs': 'c92c02cf2698a8f5e3fc777d974fc581080fbfdfa43df795fd211c0a8688eaa4',
  'game/tests/v73/browser_features.cjs': 'e432eb7f917c5e8bc6a9005e2469f4036f6f2c5638612ea05757016a15a8eb8d',
  'game/tests/v73/continuity_browser.cjs': '3d54d9ff2399971b63be70c2c247840e303f7bc8752a1d1cea30e9c43291dfbf',
};
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
async function sourceEvidence(script) {
  const filenames = new Set([
    'game/SOMA_MASSILIA_URBAIN_v0_74.html', 'game/metropole-viewer-v74.html',
    'game/build_v74.py', 'game/tools/build_metropole_viewer_v74.py',
    'game/tools/launch_cache_v74.py', 'game/tools/serve_v74.py', 'lancer.py',
    ...Object.keys(parentScripts), ...await filesBelow('game/src/v74'),
    path.relative(root, script), 'game/tests/v74/browser_provenance.cjs',
  ]);
  const toolsDir = await fs.readdir(path.join(root, 'game/tools'));
  for (const name of toolsDir) if (/^v74_.*\.py$/.test(name)) filenames.add('game/tools/' + name);
  const sources = {};
  for (const filename of [...filenames].sort()) {
    try { sources[filename] = hash(await fs.readFile(path.join(root, filename))); }
    catch (error) { if (error.code === 'ENOENT') sources[filename] = null; else throw error; }
  }
  for (const [filename, expected] of Object.entries(parentScripts)) {
    if (sources[filename] !== expected) throw Error('Frozen QA parent changed: ' + filename);
  }
  return {
    recordedAt: new Date().toISOString(),
    gitHEAD: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    branch: execFileSync('git', ['branch', '--show-current'], { cwd: root, encoding: 'utf8' }).trim(),
    script: path.relative(root, script), sources,
    aggregateSHA256: hash(JSON.stringify(sources)),
    sourceScope: 'Current v74 runtime, generation, executing QA script, provenance helper and generated HTML; frozen v73 QA inputs remain immutable.',
  };
}
module.exports = { sourceEvidence };
