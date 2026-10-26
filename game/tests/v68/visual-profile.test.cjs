'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SOURCE = path.resolve(__dirname, '../../src/v68/world-runtime.js');
const KEY = 'soma-massilia-v68-visual';
const CAMPAIGN_KEY = 'soma-massilia.continuity.v37';

function freeze(value) {
  if (value && typeof value === 'object') {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}

function load({stored, readThrows = false, writeThrows = false} = {}) {
  const state = freeze({credits: 246, settings: {v67Density: 'standard'},
    v67: {schema: 'soma-v67/1', districtVisits: {port: 3}, conversations: {'civil:1': 7},
      ambientSeen: {}, lastDistrict: 'port'}});
  const campaign = freeze({schema: 'soma-continuity/37', payload: {core: state}});
  const storage = new Map([
    [CAMPAIGN_KEY, JSON.stringify(campaign)],
    [CAMPAIGN_KEY + '.backup', '{"checkpoint":"previous"}'],
    ['soma.grouped.v64.previous', '{"grouped":"untouched"}'],
    ['soma-exploration-v62.a', '{"places":["port"]}']
  ]);
  if (stored !== undefined) storage.set(KEY, stored);
  const before = new Map(storage), reads = [], writes = [], styles = [], timers = [];
  // Simulate old/new classes surviving a DOM reuse: neutral must remove both.
  const classes = new Set(['soma-wasteland68', 'soma-cyberpunk68', 'existing-shell']);
  const localStorage = {
    getItem(key) {
      reads.push(key);
      if (readThrows) throw Object.assign(new Error('Storage unavailable'), {name: 'SecurityError'});
      return storage.has(key) ? storage.get(key) : null;
    },
    setItem(key, value) {
      writes.push([key, String(value)]);
      if (writeThrows) throw Object.assign(new Error('Storage full'), {name: 'QuotaExceededError'});
      storage.set(key, String(value));
    },
    removeItem(key) {
      throw new Error('Visual profile setup must not delete storage: ' + key);
    },
    clear() {
      throw new Error('Visual profile setup must not clear campaign storage.');
    }
  };
  const document = {
    title: '',
    querySelector: () => null,
    createElement: tag => ({tagName: tag.toUpperCase(), style: {}, dataset: {}}),
    head: {append: node => styles.push(node)},
    body: {classList: {
      remove: (...names) => names.forEach(name => classes.delete(name)),
      toggle(name, enabled) {
        const next = enabled === undefined ? !classes.has(name) : Boolean(enabled);
        if (next) classes.add(name); else classes.delete(name);
        return next;
      }
    }}
  };
  const window = {
    __SOMA_V67__: {version: '0.67.0'},
    __SOMA_ARCH68__: {referenceCount: () => 0},
    __SOMA__: {version: '0.67.0'}
  };
  const context = vm.createContext({window, document, localStorage, state, campaign,
    openModal: id => id, setTimeout: (...args) => timers.push(args)});
  vm.runInContext(fs.readFileSync(SOURCE, 'utf8'), context, {filename: SOURCE});
  return {context, api: window.__SOMA_V68__, storage, before, reads, writes,
    classes, styles, timers, state, campaign};
}

function assertProfile(result, expected) {
  assert(result.api, 'The actual runtime must complete setup and expose its public API.');
  assert.equal(result.api.ambience(), expected);
  assert.equal(result.classes.has('soma-cyberpunk68'), expected === 'cyberpunk');
  assert.equal(result.classes.has('soma-wasteland68'), false, 'The retired class must always be removed.');
  assert.equal(result.classes.has('existing-shell'), true, 'Unrelated DOM classes must survive.');
  assert.equal(result.timers.length, 0, 'Available prerequisites must complete setup without polling.');
  assert.equal(result.styles.length, 1, 'The real style installation must run.');
  assert.equal(result.styles[0].id, 'soma-v68-style');
  assert.deepEqual(result.reads, [KEY], 'Migration reads only its dedicated preference.');
  assert.equal(result.context.state, result.state);
  assert.equal(result.context.campaign, result.campaign);
  assert.equal(Object.hasOwn(result.context.state, 'v68'), false);
  for (const [key, value] of result.before) {
    if (key !== KEY) assert.equal(result.storage.get(key), value, 'Campaign storage changed: ' + key);
  }
  assert.deepEqual([...result.storage.keys()].filter(key => key !== KEY),
    [...result.before.keys()].filter(key => key !== KEY), 'No campaign keys may be added or removed.');
  assert(result.writes.every(([key]) => key === KEY), 'Only the dedicated visual preference may be written.');
}

test('an absent visual preference defaults to cyberpunk without writing storage', () => {
  const result = load();
  assertProfile(result, 'cyberpunk');
  assert.deepEqual(result.writes, []);
  assert.equal(result.storage.has(KEY), false);
});

test('the old wasteland preference migrates to cyberpunk using only its existing key', () => {
  const result = load({stored: 'wasteland'});
  assertProfile(result, 'cyberpunk');
  assert.deepEqual(result.writes, [[KEY, 'cyberpunk']]);
  assert.equal(result.storage.get(KEY), 'cyberpunk');
});

for (const stored of ['neutral', 'cyberpunk']) {
  test('an explicit ' + stored + ' preference is preserved without a write', () => {
    const result = load({stored});
    assertProfile(result, stored);
    assert.deepEqual(result.writes, []);
    assert.equal(result.storage.get(KEY), stored);
  });
}

for (const stored of ['unknown-profile', '']) {
  test('an unknown preference ' + JSON.stringify(stored) + ' uses cyberpunk without rewriting it', () => {
    const result = load({stored});
    assertProfile(result, 'cyberpunk');
    assert.deepEqual(result.writes, []);
    assert.equal(result.storage.get(KEY), stored);
  });
}

test('a storage read failure leaves cyberpunk available and campaign data intact', () => {
  const result = load({stored: 'neutral', readThrows: true});
  assertProfile(result, 'cyberpunk');
  assert.deepEqual(result.writes, []);
  assert.deepEqual([...result.storage], [...result.before]);
});

test('a failed legacy migration write keeps cyberpunk usable without losing saved data', () => {
  const result = load({stored: 'wasteland', writeThrows: true});
  assertProfile(result, 'cyberpunk');
  assert.deepEqual(result.writes, [[KEY, 'cyberpunk']]);
  assert.deepEqual([...result.storage], [...result.before]);
});

test('the installed options hook preserves the underlying modal operation', () => {
  const result = load();
  assert.equal(result.context.openModal('options'), 'options');
  assertProfile(result, 'cyberpunk');
  assert.deepEqual(result.writes, []);
});
