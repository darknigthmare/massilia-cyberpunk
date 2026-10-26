'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const K = require('../../src/v69/roof-core.js');
const originalAppearance = K.appearance;
const M = require('../../src/v70/material-extension-core.js');
const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);

test('CSS aqua is a declared nonemissive colour with exact source spelling', () => {
  const p = {'building:colour': ' AQUA ', 'roof:color': 'aqua'};
  const a = M.appearance(p, 'source');
  assert.deepEqual(a.wall, [0, 1, 1]); assert.deepEqual(a.roof, [0, 1, 1]);
  assert.deepEqual(M.parseColour('aqua'), rgb('#00ffff'));
  assert.equal(a.wallColourEvidence.tag, 'building:colour');
  assert.equal(a.wallColourEvidence.value, ' AQUA ');
  assert.equal(a.roofColourEvidence.tag, 'roof:color');
  assert.equal(a.wallColourEvidence.interpretation, 'declared-colour');
  assert.equal(a.wallColourEvidence.colourMeasurementVerified, false);
  assert(a.wall.every(x => x <= 1)); assert(a.roof.every(x => x <= 1));
});

test('every valid explicit colour stays prioritary over façade and generic materials', () => {
  for (const colour of ['red', '#123456', '#abc', 'rgb(20, 30, 40)', 'aqua']) {
    const p = {'building:colour': colour, 'building:facade:material': 'glass',
      'building:material': 'plastic', 'roof:colour': colour, 'roof:material': 'grass'};
    const a = M.appearance(p, 'source');
    assert.deepEqual(a.wall, M.parseColour(colour)); assert.deepEqual(a.roof, M.parseColour(colour));
    assert.equal(a.wallSource, 'osm-building-colour'); assert.equal(a.roofSource, 'osm-roof-colour');
  }
  const alias = M.appearance({'building:colour': 'unknown', 'building:color': 'aqua',
    'roof:colour': 'invalid', 'roof:color': 'blue'});
  assert.equal(alias.wallColourEvidence.tag, 'building:color');
  assert.equal(alias.roofColourEvidence.tag, 'roof:color');
});

test('the source façade glass declaration takes priority over a generic building material', () => {
  const p = {'building:facade:material': ' GLASS ', 'building:material': 'stone'};
  const a = M.appearance(p, 'source');
  assert.deepEqual(a.wall, K.appearance({'building:material': 'glass'}, 'source').wall);
  assert.equal(a.wallSource, 'osm-building-facade-material');
  assert.equal(a.wallColourEvidence.tag, 'building:facade:material');
  assert.equal(a.wallColourEvidence.value, ' GLASS ');
  assert.equal(a.wallColourEvidence.interpretation, 'material-palette');
  assert.equal(a.wallColourEvidence.materialIsColourMeasurement, false);
  assert.equal(a.wallColourEvidence.surfaceModel, 'opaque-colour-only');
  assert.equal(a.wallColourEvidence.textureSurveyed, false);
});

test('plastic and the newly supported roof materials use explicitly interpreted palettes', () => {
  const plastic = M.appearance({'building:material': 'plastic'});
  assert.deepEqual(plastic.wall, rgb('#c7cec8'));
  assert.equal(plastic.wallColourEvidence.tag, 'building:material');
  assert.equal(plastic.wallColourEvidence.colourAccuracy, 'interpreted');
  for (const [name, hex] of Object.entries({grass:'#688458', gravel:'#929189',
    acrylic_glass:'#a9c9cb', fabric:'#c8bc9e', plastic:'#c7cec8'})) {
    const a = M.appearance({'roof:material': name});
    assert.deepEqual(a.roof, rgb(hex)); assert.equal(a.roofSource, 'osm-roof-material');
    assert.equal(a.roofColourEvidence.tag, 'roof:material');
    assert.equal(a.roofColourEvidence.value, name);
    assert.equal(a.roofColourEvidence.interpretation, 'material-palette');
    assert.equal(a.roofColourEvidence.materialIsColourMeasurement, false);
  }
});

test('unknown and compound tags retain the established fallback without colour guessing', () => {
  for (const value of ['unknown', 'glass;stone', '__proto__', 'constructor', '', null, {}, 1]) {
    const p = {'building:facade:material': value, 'building:material': value,
      'roof:material': value, 'building:colour': value, 'roof:colour': value};
    const a = M.appearance(p, 'source'), legacy = K.appearance(p, 'source');
    assert.deepEqual(a.wall, legacy.wall); assert.deepEqual(a.roof, legacy.roof);
    assert.equal(a.wallSource, legacy.wallSource); assert.equal(a.roofSource, legacy.roofSource);
  }
  const fallback = M.appearance({'building:facade:material': 'unmapped', 'building:material': 'stone'});
  assert.equal(fallback.wallSource, 'osm-building-material');
  assert.equal(fallback.wallColourEvidence.tag, 'building:material');
  assert.equal(fallback.wallColourEvidence.interpretation, 'material-palette');
});

test('source geometry, height semantics and the unchanged core are never mutated', () => {
  const p = Object.freeze({'building:facade:material':'glass', 'building:material':'plastic',
    'roof:material':'gravel', height:'12', 'roof:height':'3',
    'soma:geometry_sha256':'immutable-geometry', 'soma:mesh53':Object.freeze([])});
  const before = JSON.stringify(p), a = M.appearance(p, 'stable-id'), b = M.appearance(p, 'stable-id');
  assert.equal(JSON.stringify(p), before); assert.equal(K.appearance, originalAppearance);
  assert.deepEqual(a, b); assert.notEqual(a.wall, b.wall); assert.notEqual(a.roof, b.roof);
  a.wall[0] = 0; a.roof[0] = 0;
  assert.deepEqual(M.appearance(p, 'stable-id'), b);
  assert.deepEqual(b.accent, K.appearance(p, 'stable-id').accent);
  assert.equal(b.lightingSource, 'interpreted-cyberpunk-lighting');
  assert.deepEqual(b.trim, b.wall.map(x => x * .71));
  assert.equal(Object.hasOwn(b, 'height'), false); assert.equal(Object.hasOwn(b, 'groundAltitude'), false);
});

test('existing material palettes remain intact and gain an honest interpretation label', () => {
  const p = {'building:material':'limestone', 'roof:material':'roof_tiles'};
  const a = M.appearance(p, 'source'), legacy = K.appearance(p, 'source');
  assert.deepEqual(a.wall, legacy.wall); assert.deepEqual(a.roof, legacy.roof);
  assert.equal(a.wallColourEvidence.interpretation, 'material-palette');
  assert.equal(a.roofColourEvidence.interpretation, 'material-palette');
  assert.equal(a.wallColourEvidence.colourAccuracy, 'interpreted');
  assert.equal(a.roofColourEvidence.value, 'roof_tiles');
  assert.equal(M.appearance(null).wallColourEvidence.interpretation, 'regional-palette');
});

test('browser loading publishes a separate API and leaves roof and terrain helpers intact', () => {
  const fs = require('node:fs'), vm = require('node:vm');
  const source = fs.readFileSync(require.resolve('../../src/v70/material-extension-core.js'), 'utf8');
  const before = {appearance: K.appearance, roofPlan: K.roofPlan, roofTriangles: K.roofTriangles,
    wallSegments: K.wallSegments, roofDimensions: K.roofDimensions};
  const window = {__SOMA_ARCH68_CORE__: K};
  vm.runInNewContext(source, {window});
  assert.equal(window.__SOMA_MATERIAL70_CORE__.VERSION, '0.70.0');
  const a = window.__SOMA_MATERIAL70_CORE__.appearance({'building:material':'plastic'});
  assert.equal(a.wallSource, 'osm-building-material');
  assert.equal(a.wallColourEvidence.interpretation, 'material-palette');
  for (const [key, value] of Object.entries(before)) assert.equal(K[key], value);
  assert.equal(Object.hasOwn(window.__SOMA_MATERIAL70_CORE__, 'roofPlan'), false);
  assert.equal(Object.hasOwn(window.__SOMA_MATERIAL70_CORE__, 'sample'), false);
  assert.throws(() => vm.runInNewContext(source, {window:{}}), /Architecture core must load/);
});
