'use strict';

// Each suite qualifies its own real pages. Frozen75 evidence is a baseline;
// current PASS requires HTML ↔ report ↔ actual producing inputs before/after.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../../..');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const canonical = value => JSON.stringify(value, (key, item) => item && !Array.isArray(item) && typeof item === 'object'
  ? Object.fromEntries(Object.keys(item).sort().map(name => [name, item[name]])) : item);
const parentScripts = Object.freeze({
  'game/tests/v75/browser_smoke.cjs': '01435b90abc4e8592e1aa9ae6967e58e4832f787a1cf9fc2c1d94b00995b65e2',
  'game/tests/v75/browser_features.cjs': '2bb2234e4df97f72826562c039f0b77c394cc25d75cc5767b32ccd04359b7247',
  'game/tests/v75/browser_missions.cjs': '59ed8d4911cb7319d09d01a4fc082d99f8b3f8359b85c8fabd9d92975d65b0ba',
  'game/tests/v75/browser_mechanics.cjs': '3a95e8dbb84537792c8d92c0dfc3d08e19f1a7217b6fb33977f228de8c88dbe6',
  'game/tests/v75/browser_terrain.cjs': '7cc4c6ebc623170da861af400a3224c8ab731007174d315d83cd65cfa79b63ce',
  'game/tests/v75/browser_sniper.cjs': '565ca204f6931303ca08490b5b17f589049187da1fc82e51e1d475ce4842767e',
  'game/tests/v75/continuity_browser.cjs': 'de32fce76717aaf1fc454011c0c5dedf443c19401e02e9c394ce495050f7fbb8',
  'game/tests/v75/browser_provenance.cjs': 'caf430fcb835d4760a935a728501154d166ee802affe27c374ec50905ee79bc3',
});
// Export-page hashes come from the frozen75 browser evidence and delivery.
const parentPages = Object.freeze({
  'game/SOMA_MASSILIA_URBAIN_v0_70.html': 'c73fcd0b771d83aa1849130934ca432c3dcb70f40905e9638792eca4afc01c2a',
  'game/SOMA_MASSILIA_URBAIN_v0_71.html': '6bd174abf56504640edbc8c92a4d9279fb76f0d6b079f3d4ae4bbb5a948c333d',
  'game/SOMA_MASSILIA_URBAIN_v0_73.html': 'b629b30434dddb8eee66402afc1f5c9eaf47389b60a3fe9125f039cdc3f4e0f2',
  'game/SOMA_MASSILIA_URBAIN_v0_74.html': '1b776a1b8b3c2861093e1670d1b203025b158bd0fb0f464f0ab3d58086139330',
  'game/SOMA_MASSILIA_URBAIN_v0_75.html': 'fe4ba1538007c85c14d4d39aca0017f5bb2ec090986f6181896ce46fa1cb9aad',
  'game/metropole-viewer-v75.html': 'd18ffa35f7243855e49cb174ab6d69b9f14e8e8ed467a38ebdb789bbb7600de3',
});
const currentPages = Object.freeze(['game/SOMA_MASSILIA_URBAIN_v0_76.html', 'game/metropole-viewer-v76.html']);
function validateEvidence(sources, frozen = { ...parentScripts, ...parentPages }) {
  for (const [filename, expected] of Object.entries(frozen)) {
    if (sources[filename] !== expected) throw Error('Frozen QA input changed or missing: ' + filename);
  }
  for (const filename of currentPages) {
    if (!/^[a-f0-9]{64}$/.test(sources[filename] || '')) throw Error('Built QA page missing: ' + filename);
  }
}
function producerFiles(inputs) {
  const files = {};
  function visit(snapshot) {
    if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) return;
    for (const [key, value] of Object.entries(snapshot)) {
      if (key === 'reusedWorldManifest') files['game/data/v69/world/manifest.json'] = value;
      else if (value && !Array.isArray(value) && typeof value === 'object' && typeof value.sha256 === 'string' && Number.isInteger(value.bytes)) {
        if (key.startsWith('/') || key.split('/').includes('..') || !key.includes('.')) throw Error('Invalid producer path: ' + key);
        const filename = 'game/' + key;
        if (files[filename] && canonical(files[filename]) !== canonical(value)) throw Error('Conflicting producer evidence: ' + filename);
        files[filename] = value;
      } else visit(value);
    }
  }
  visit(inputs);
  return files;
}
function validateBuildEvidence(report, sources, html, actualInputs) {
  if (report.version !== '0.76.0' || report.output !== path.basename(html) || report.sha256 !== sources[html]) throw Error('Built QA page and build report diverge: ' + html);
  const inputs = report.inputs;
  if (!inputs?.sources76 || Object.keys(inputs.sources76).length < 1) throw Error('Built QA page has no source input evidence: ' + html);
  if (!Array.isArray(inputs.modules76) || !inputs.modules76.length || new Set(inputs.modules76).size !== inputs.modules76.length || inputs.modules76.some(name => !/^[a-z][a-z0-9-]*$/.test(name) || !inputs.sources76['src/v76/' + name + '.js'])) throw Error('Built QA page has incomplete module evidence: ' + html);
  for (const [filename, expected] of Object.entries(producerFiles(inputs))) {
    if (sources[filename] !== expected.sha256) throw Error('Built QA page uses stale producer input: ' + filename);
  }
  if (!actualInputs || canonical(inputs) !== canonical(actualInputs)) throw Error('Built QA page does not match actual producing inputs: ' + html);
}
async function sourceEvidence(script) {
  // Calling the real owner's read-only input inventory also checks its frozen
  // parents. A report cannot qualify itself by omitting a newly used producer.
  const actualInputs = JSON.parse(execFileSync('python3', ['-B', '-S', '-c',
    'import json,sys;sys.path.insert(0,"game");import build_v76;print(json.dumps(build_v76.inputs(),sort_keys=True))'],
    { cwd: root, encoding: 'utf8', maxBuffer: 4 * 1024 * 1024, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } }));
  const filenames = new Set([
    ...currentPages, ...Object.keys(parentScripts), ...Object.keys(parentPages),
    ...Object.keys(producerFiles(actualInputs)), 'lancer.py',
    'game/data/v76/BUILD_REPORT.json', 'game/data/v76/VIEWER_BUILD_REPORT.json',
    path.relative(root, script), 'game/tests/v76/browser_provenance.cjs',
  ]);
  const sources = {};
  for (const filename of [...filenames].sort()) {
    try { sources[filename] = hash(await fs.readFile(path.join(root, filename))); }
    catch (error) { if (error.code === 'ENOENT') sources[filename] = null; else throw error; }
  }
  validateEvidence(sources);
  const artifacts = [];
  for (const [relative, html] of [['BUILD_REPORT.json', currentPages[0]], ['VIEWER_BUILD_REPORT.json', currentPages[1]]]) {
    const report = JSON.parse(await fs.readFile(path.join(root, 'game/data/v76', relative), 'utf8'));
    validateBuildEvidence(report, sources, html, actualInputs);
    artifacts.push({ html, sha256: report.sha256, report: 'game/data/v76/' + relative, actualProducerInputsSHA256: hash(canonical(actualInputs)) });
  }
  return {
    recordedAt: new Date().toISOString(),
    gitHEAD: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    branch: execFileSync('git', ['branch', '--show-current'], { cwd: root, encoding: 'utf8' }).trim(),
    script: path.relative(root, script), sources, aggregateSHA256: hash(canonical(sources)), artifacts,
    modules76: actualInputs.modules76,
    sourceScope: 'Both actual76 pages and reports bound to the real build76 input inventory, all inherited producer fingerprints, exact frozen75 QA and pages, authentic70/71/73/74/75 export pages, executing QA script and shared helper.',
  };
}
async function finishEvidence(report, script) {
  try {
    report.provenanceFinished = await sourceEvidence(script);
    report.sourceSetUnchanged = report.provenance?.aggregateSHA256 === report.provenanceFinished.aggregateSHA256;
    if (!report.sourceSetUnchanged) throw Error('Tested source set changed during browser execution.');
  } catch (error) {
    report.passed = false; report.sourceSetUnchanged = false;
    report.provenanceFailure = String(error.stack || error); process.exitCode = 1;
  }
}
module.exports = { sourceEvidence, finishEvidence, validateEvidence, validateBuildEvidence, producerFiles, parentScripts, parentPages, currentPages };
