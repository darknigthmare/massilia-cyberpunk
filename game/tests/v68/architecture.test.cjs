'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const Core = require('../../src/v68/architecture-core.js');

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);
const SOURCE = 'test-source-receipt';
const ID = 'osm/way/42';
const SHA = 'test-canonical-geometry';

function record(cellId, ring, walls, overrides = {}) {
  return {
    cellId, sourceReceipt: {sha256: SOURCE}, v53Synthetic: false,
    featureCollection: {type: 'FeatureCollection', features: [{
      id: ID, type: 'Feature', properties: {
        canonical_id: ID, 'soma:geometry_sha256': SHA, 'soma:layer': 'buildings',
        'soma:mesh53': [{ringsL93: [ring], wallsL93: walls}], ...overrides
      }
    }]}
  };
}

function splitRecords() {
  return [
    record('west', [[0, 0], [5, 0], [5, 10], [0, 10], [0, 0]], [
      [[0, 0], [5, 0]], [[5, 10], [0, 10]], [[0, 10], [0, 0]]
    ]),
    record('east', [[5, 0], [10, 0], [10, 10], [5, 10], [5, 0]], [
      [[5, 0], [10, 0]], [[10, 0], [10, 10]], [[10, 10], [5, 10]]
    ])
  ];
}

function reference(records = splitRecords()) {
  return [...Core.referenceIndex(records).values()][0];
}

const SKILLION = {'roof:shape': 'skillion', height: '12', 'roof:height': '3', 'roof:direction': '90'};
const DIMENSIONS = {height: 12, minHeight: 0, valid: true};

test('colour parser accepts sourced colours and rejects malformed or executable CSS', () => {
  assert.deepEqual(Core.parseColour('#abc'), [170 / 255, 187 / 255, 204 / 255]);
  assert.deepEqual(Core.parseColour('#Af8071'), [175 / 255, 128 / 255, 113 / 255]);
  assert.deepEqual(Core.parseColour('light yellow'), [1, 1, 224 / 255]);
  assert.deepEqual(Core.parseColour('rgb(255, 128, 0)'), [1, 128 / 255, 0]);
  for (const value of [null, {}, 12, '#ffff', '#xyzxyz', 'transparent', 'rgb(256,0,0)',
    'rgb(-1,0,0)', 'url(javascript:alert(1))', '__proto__', '#fff; color:red']) {
    assert.equal(Core.parseColour(value), null);
  }
});

test('appearance prioritises OSM colour, then material, then an explicit interpretation', () => {
  const colour = Core.appearance({'building:colour': '#123456', 'building:material': 'stone',
    'roof:colour': '#cc6666', 'roof:material': 'roof_tiles'}, '42');
  assert.deepEqual(colour.wall, Core.parseColour('#123456'));
  assert.equal(colour.wallSource, 'osm-building-colour');
  assert.equal(colour.roofSource, 'osm-roof-colour');
  const material = Core.appearance({'building:colour': 'invalid', 'building:material': 'plaster',
    'roof:material': 'roof_tiles'}, '42');
  assert.equal(material.wallSource, 'osm-building-material');
  assert.equal(material.roofSource, 'osm-roof-material');
  const fallback = Core.appearance({}, '42');
  assert.equal(fallback.wallSource, 'interpreted-marseille-palette');
  assert.deepEqual(fallback, Core.appearance({}, '42'));
  assert.ok([...fallback.wall, ...fallback.roof, ...fallback.trim].every(value => value >= 0 && value <= 1));
});

test('canonical reference joins SOURCE walls across cells without moving source geometry', () => {
  const records = splitRecords(), snapshot = JSON.stringify(records);
  const index = Core.referenceIndex(new Map(records.map(item => [item.cellId, item])));
  assert.equal(index.size, 1);
  const ref = [...index.values()][0];
  assert.equal(ref.complete, true);
  assert.equal(ref.outerCount, 1);
  assert.deepEqual(ref.bounds, [0, 0, 10, 10]);
  assert.equal(ref.walls.length, 6);
  assert.equal(JSON.stringify(records), snapshot);
  assert.equal(Core.referenceIndex([...records].reverse()).values().next().value.complete, true);
});

test('clipped cell rings do not falsely close an incomplete SOURCE wall chain', () => {
  const ref = reference(splitRecords().slice(0, 1));
  assert.equal(ref.complete, false);
  const plan = Core.roofPlan(SKILLION, DIMENSIONS, ref);
  assert.equal(plan.modelled, false);
  assert.equal(plan.reason, 'incomplete-canonical-reference');
  assert.equal(plan.heightAt(5, 5), 12);
});

test('synthetic records are excluded and separate source receipts never merge', () => {
  const records = splitRecords();
  const synthetic = structuredClone(records[0]);
  synthetic.v53Synthetic = true;
  assert.equal(Core.referenceIndex([synthetic]).size, 0);
  records[1].sourceReceipt.sha256 = 'another-receipt';
  assert.equal(Core.referenceIndex(records).size, 2);
  assert.ok([...Core.referenceIndex(records).values()].every(ref => !ref.complete));
});

test('duplicate fragments do not create non-manifold canonical walls', () => {
  const records = splitRecords();
  assert.equal(reference([...records, structuredClone(records[0])]).complete, true);
});

test('skillion direction 90 slopes DOWN to the east and never exceeds total height', () => {
  const plan = Core.roofPlan(SKILLION, DIMENSIONS, reference());
  assert.equal(plan.modelled, true);
  assert.equal(plan.shape, 'skillion');
  close(plan.eave, 9);
  close(plan.heightAt(0, 5), 12);
  close(plan.heightAt(10, 5), 9);
  close(plan.heightAt(5, 5), 10.5);
  close(plan.heightAt(-1, 5), 12);
  close(plan.heightAt(11, 5), 9);
});

test('north/south roof directions respect Lambert northing rather than local south-z', () => {
  const north = Core.roofPlan({...SKILLION, 'roof:direction': '0'}, DIMENSIONS, reference());
  close(north.heightAt(5, 10), 9);
  close(north.heightAt(5, 0), 12);
  const south = Core.roofPlan({...SKILLION, 'roof:direction': '180'}, DIMENSIONS, reference());
  close(south.heightAt(5, 10), 12);
  close(south.heightAt(5, 0), 9);
});

test('multicell roof profile is identical at shared global coordinates', () => {
  const records = splitRecords();
  const index = Core.referenceIndex(records);
  const plans = records.map(item => Core.roofPlan(SKILLION, DIMENSIONS,
    index.get(Core.referenceKey(item.featureCollection.features[0].properties, ID, item))));
  const westProjector = {toMetric: ([x, z]) => [2.5 + x, 5 - z]};
  const eastProjector = {toMetric: ([x, z]) => [7.5 + x, 5 - z]};
  const west = Core.roofTriangles([[[2.5, 5], [2.5, -5], [-2.5, 5]]], plans[0], westProjector);
  const east = Core.roofTriangles([[[-2.5, 5], [2.5, 5], [-2.5, -5]]], plans[1], eastProjector);
  close(west[0][0][1], east[0][0][1]);
  close(west[0][1][1], east[0][2][1]);
  close(west[0][0][1], 10.5);
});

test('courtyard source loops stay holes because prepared triangles are reused unchanged', () => {
  const outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]];
  const inner = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]];
  const walls = [outer, inner].flatMap(ring => ring.slice(1).map((point, i) => [ring[i], point]));
  const item = record('courtyard', outer, walls);
  item.featureCollection.features[0].properties['soma:mesh53'][0].ringsL93.push(inner);
  const ref = reference([item]);
  assert.equal(ref.complete, true);
  assert.equal(ref.hasHoles, true);
  assert.equal(ref.outerCount, 1);
  const strips = [
    [[0, 0], [10, 0], [7, 3]], [[0, 0], [7, 3], [3, 3]],
    [[10, 0], [10, 10], [7, 7]], [[10, 0], [7, 7], [7, 3]],
    [[10, 10], [0, 10], [3, 7]], [[10, 10], [3, 7], [7, 7]],
    [[0, 10], [0, 0], [3, 3]], [[0, 10], [3, 3], [3, 7]]
  ];
  const snapshot = JSON.stringify(strips);
  const result = Core.roofTriangles(strips, Core.roofPlan(SKILLION, DIMENSIONS, ref), {toMetric: point => point});
  assert.deepEqual(result.map(triangle => triangle.map(([x, , z]) => [x, z])), strips);
  const area = triangle => Math.abs((triangle[1][0] - triangle[0][0]) * (triangle[2][1] - triangle[0][1]) -
    (triangle[2][0] - triangle[0][0]) * (triangle[1][1] - triangle[0][1])) / 2;
  close(strips.reduce((sum, triangle) => sum + area(triangle), 0), 84);
  assert.equal(JSON.stringify(strips), snapshot);
});

test('explicit metres, centimetres and feet are accepted without adding roof height twice', () => {
  const cm = Core.roofPlan({...SKILLION, height: '1200 cm', 'roof:height': '300 cm'}, DIMENSIONS, reference());
  close(cm.eave, 9);
  const feet = Core.roofPlan({...SKILLION, height: '40 ft', 'roof:height': '10 ft'},
    {height: 12.192, minHeight: 0, valid: true}, reference());
  assert.equal(feet.modelled, true);
  close(feet.eave, 9.144);
  close(feet.heightAt(0, 0), 12.192);
});

test('roof-only building parts allow the eave to equal min_height', () => {
  const plan = Core.roofPlan({...SKILLION, height: '10', min_height: '9', 'roof:height': '1'},
    {height: 10, minHeight: 9, valid: true}, reference());
  assert.equal(plan.modelled, true);
  close(plan.eave, 9);
  close(plan.heightAt(10, 5), 9);
  close(plan.heightAt(0, 5), 10);
  const step = Core.roofPlan({...SKILLION, height: '0.4', 'roof:height': '0.4'},
    {height: 0.4, minHeight: 0, valid: true}, reference());
  assert.equal(step.modelled, true);
  close(step.eave, 0);
});

test('missing tags, impossible dimensions and unsupported shapes remain explicit flat fallbacks', () => {
  const invalid = [
    [{...SKILLION, height: undefined}, DIMENSIONS, 'explicit-total-height-required'],
    [{...SKILLION, height: '20'}, DIMENSIONS, 'explicit-total-height-required'],
    [{...SKILLION, 'roof:height': '-1'}, DIMENSIONS, 'invalid-or-missing-roof-height'],
    [{...SKILLION, 'roof:height': '13'}, DIMENSIONS, 'invalid-or-missing-roof-height'],
    [{...SKILLION, 'roof:direction': 'many'}, DIMENSIONS, 'roof-direction-required'],
    [{...SKILLION, 'roof:direction': '-90'}, DIMENSIONS, 'roof-direction-required'],
    [{...SKILLION, 'roof:shape': 'gabled'}, DIMENSIONS, 'unsupported-roof-shape'],
    [{}, DIMENSIONS, 'roof-shape-unavailable'],
    [SKILLION, {...DIMENSIONS, minHeight: 12}, 'invalid-dimensions'],
    [SKILLION, {...DIMENSIONS, height: NaN}, 'invalid-dimensions'],
    [SKILLION, {...DIMENSIONS, height: Infinity}, 'invalid-dimensions']
  ];
  for (const [properties, dimensions, reason] of invalid) {
    const plan = Core.roofPlan(properties, dimensions, reference());
    assert.equal(plan.modelled, false);
    assert.equal(plan.reason, reason);
    assert.equal(plan.shape, 'flat');
    assert.ok(Number.isFinite(plan.heightAt(0, 0)));
  }
  const flat = Core.roofPlan({'roof:shape': 'flat'}, DIMENSIONS);
  assert.equal(flat.modelled, true);
  assert.equal(flat.reason, 'osm-flat');
  close(flat.heightAt(0, 0), 12);
});

test('roof helper rejects invalid triangles and missing projections instead of producing NaN geometry', () => {
  const plan = Core.roofPlan({'roof:shape': 'flat'}, DIMENSIONS);
  assert.throws(() => Core.roofTriangles([], plan, {}), TypeError);
  assert.throws(() => Core.roofTriangles([[[0, 0], [1, 0]]], plan, {toMetric: point => point}), TypeError);
  assert.throws(() => Core.roofTriangles([[[0, 0], [1, 0], [0, NaN]]], plan, {toMetric: point => point}), TypeError);
});

const facadeProjector = {toMetric: ([x, z]) => [891000 + x, 6246000 - z]};

function assertSameFacadeCoverage(whole, fragments) {
  const slots = new Map();
  for (const panel of fragments) {
    const sum = slots.get(panel.slot) || {width: 0, x: 0, z: 0};
    sum.width += panel.width;
    sum.x += panel.center[0] * panel.width;
    sum.z += panel.center[1] * panel.width;
    slots.set(panel.slot, sum);
  }
  assert.equal(slots.size, whole.length);
  for (const panel of whole) {
    const merged = slots.get(panel.slot);
    assert.ok(merged, `Missing facade slot ${panel.slot}`);
    close(merged.width, panel.width);
    close(merged.x / merged.width, panel.center[0]);
    close(merged.z / merged.width, panel.center[1]);
  }
}

test('facade cadence has the same coverage on a whole wall and two cell fragments', () => {
  const a = [0, 0], b = [24, 0];
  const whole = Core.facadePanels(a, b, facadeProjector, ID);
  assert.ok(whole.length > 3);
  const split = [whole[2].center[0] + whole[2].width / 3, 0];
  const fragments = [
    ...Core.facadePanels(a, split, facadeProjector, ID),
    ...Core.facadePanels(split, b, facadeProjector, ID)
  ];
  assertSameFacadeCoverage(whole, fragments);
  const crossing = fragments.filter(panel => panel.slot === whole[2].slot);
  assert.equal(crossing.length, 2);
  close(crossing[0].center[0] + crossing[0].width / 2, split[0]);
  close(crossing[1].center[0] - crossing[1].width / 2, split[0]);
  assert.ok(fragments.every(panel => panel.width > 0 && panel.width <= 1.1 + 1e-8));
});

test('facade slots and offsets are independent of source endpoint order', () => {
  for (const [a, b] of [[[0, 0], [24, 0]], [[0, 24], [0, 0]], [[3, 5], [27, 37]]]) {
    for (const offset of [-0.726, 0, 0.726]) {
      assert.deepEqual(Core.facadePanels(a, b, facadeProjector, ID, 0.308, 3.6, offset),
        Core.facadePanels(b, a, facadeProjector, ID, 0.308, 3.6, offset));
    }
  }
});

test('oblique facade fragments retain metric cadence, panel width and source coordinates', () => {
  const a = [3, 5], b = [27, 37], split = [13.2, 18.6];
  const snapshot = JSON.stringify([a, b, split]);
  for (const [width, offset] of [[1.1, 0], [0.308, -0.726], [0.308, 0.726], [1.232, 0]]) {
    const whole = Core.facadePanels(a, b, facadeProjector, ID, width, 3.6, offset);
    const fragments = [
      ...Core.facadePanels(a, split, facadeProjector, ID, width, 3.6, offset),
      ...Core.facadePanels(split, b, facadeProjector, ID, width, 3.6, offset)
    ];
    assertSameFacadeCoverage(whole, fragments);
    assert.ok(whole.every(panel => panel.width <= width + 1e-8));
  }
  assert.equal(JSON.stringify([a, b, split]), snapshot);
});

test('facade offsets use the canonical metric tangent and add no artificial edge margin', () => {
  const whole = Core.facadePanels([0, 0], [24, 0], facadeProjector, ID);
  const interior = whole.find(panel => panel.center[0] > 5 && panel.center[0] < 19);
  const moved = Core.facadePanels([0, 0], [24, 0], facadeProjector, ID, 1.1, 3.6, 0.726)
    .find(panel => panel.slot === interior.slot);
  close(moved.center[0] - interior.center[0], 0.726);
  close(moved.width, 1.1);
  const center = interior.center[0];
  const tiny = Core.facadePanels([center - 0.03, 0], [center + 0.03, 0], facadeProjector, ID);
  assert.equal(tiny.length, 1);
  close(tiny[0].width, 0.06);
  close(tiny[0].center[0], center);
});

test('facade metre spacing stays fixed when a source wall is extended', () => {
  const short = Core.facadePanels([0, 0], [24, 0], facadeProjector, ID);
  const longer = Core.facadePanels([-20, 0], [40, 0], facadeProjector, ID);
  for (const panel of short.filter(panel => panel.width > 1.09)) {
    const same = longer.find(candidate => candidate.slot === panel.slot);
    close(same.center[0], panel.center[0]);
  }
  for (let i = 1; i < longer.length - 1; i++) {
    close(longer[i].center[0] - longer[i - 1].center[0], 3.6);
  }
  assert.notDeepEqual(short, Core.facadePanels([0, 0], [24, 0], facadeProjector, 'osm/way/another'));
});

test('facade invalid dimensions cannot create runaway geometry or mutate endpoints', () => {
  const a = [0, 0], b = [24, 0];
  for (const [width, spacing, offset] of [[0, 3.6, 0], [-1, 3.6, 0], [Infinity, 3.6, 0],
    [1.1, 0, 0], [1.1, -1, 0], [1.1, 3.6, NaN]]) {
    assert.throws(() => Core.facadePanels(a, b, facadeProjector, ID, width, spacing, offset), TypeError);
  }
  assert.throws(() => Core.facadePanels(a, b, facadeProjector, ID, 1, 1e-9), RangeError);
  assert.throws(() => Core.facadePanels([NaN, 0], b, facadeProjector, ID), TypeError);
  assert.throws(() => Core.facadePanels(a, b, {}, ID), TypeError);
  assert.deepEqual(Core.facadePanels(a, a, facadeProjector, ID), []);
  const mutatingProjector = {toMetric(point) {point[0] += 891000; point[1] -= 6246000; return point;}};
  Core.facadePanels(a, b, mutatingProjector, ID);
  assert.deepEqual(a, [0, 0]);
  assert.deepEqual(b, [24, 0]);
});

test('cyberpunk lighting leaves existing OSM and regional material RGB values unchanged', () => {
  const p = {'building:colour': '#123456', 'roof:colour': '#cc6666', canonical_id: ID};
  const before = JSON.stringify(p), material = Core.appearance(p, 42);
  assert.deepEqual(material.wall, Core.parseColour('#123456'));
  assert.deepEqual(material.roof, Core.parseColour('#cc6666'));
  assert.deepEqual(material.trim, Core.parseColour('#123456').map(channel => channel * 0.71));
  assert.equal(material.wallSource, 'osm-building-colour');
  assert.equal(material.roofSource, 'osm-roof-colour');
  const sourced = Core.appearance({'building:material': 'plaster', 'roof:material': 'roof_tiles'}, 42);
  assert.deepEqual(sourced.wall, Core.parseColour('#d8c7aa'));
  assert.deepEqual(sourced.roof, Core.parseColour('#b66f51'));
  assert.equal(sourced.wallSource, 'osm-building-material');
  assert.equal(sourced.roofSource, 'osm-roof-material');
  const regional = Core.appearance({}, 42);
  assert.deepEqual(regional.wall, Core.parseColour('#d5c8ad'));
  assert.deepEqual(regional.roof, Core.parseColour('#b47b59'));
  assert.equal(regional.wallSource, 'interpreted-marseille-palette');
  assert.equal(regional.roofSource, 'interpreted-marseille-palette');
  assert.equal(material.lightingSource, 'interpreted-cyberpunk-lighting');
  assert.equal(JSON.stringify(p), before);
});

test('canonical identity fixes building accent families independently of the appearance seed', () => {
  const a = Core.appearance({canonical_id: ID}, 'fragment-A');
  const b = Core.appearance({canonical_id: ID}, 'fragment-B');
  assert.deepEqual(a.accent, b.accent);
  assert.deepEqual(a.secondaryAccent, b.secondaryAccent);
  assert.notDeepEqual(a.accent, a.secondaryAccent);
  for (const colour of [a.accent, a.secondaryAccent, a.windowWarm]) {
    assert.ok(colour.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 1.9));
    assert.ok(Math.max(...colour) > 1.25);
  }
  assert.ok(a.windowDark.every(channel => channel >= 0 && channel < 1.25));
  const original = b.accent.slice();
  a.accent[0] = 999;
  assert.deepEqual(Core.appearance({canonical_id: ID}).accent, original);
});

test('window lighting stays identical across cell fragments sharing a global facade slot', () => {
  const whole = Core.facadePanels([0, 0], [24, 0], facadeProjector, ID);
  const split = [whole[2].center[0] + whole[2].width / 3, 0];
  const fragments = [
    ...Core.facadePanels([0, 0], split, facadeProjector, ID),
    ...Core.facadePanels(split, [24, 0], facadeProjector, ID)
  ];
  for (let row = 0; row < 6; row++) {
    const expected = new Map(whole.map(panel => [panel.slot, Core.windowLight(ID, row, panel.slot)]));
    for (const panel of fragments) assert.deepEqual(Core.windowLight(ID, row, panel.slot), expected.get(panel.slot));
  }
});

test('window lighting is independent of call order and varies by source and floor', () => {
  const requests = Array.from({length: 50}, (_, i) => ({source: ID, row: i % 6, slot: i - 25}));
  const expected = requests.map(({source, row, slot}) => Core.windowLight(source, row, slot));
  for (let i = requests.length - 1; i >= 0; i--) {
    const {source, row, slot} = requests[i];
    assert.deepEqual(Core.windowLight(source, row, slot), expected[i]);
  }
  const floorA = Array.from({length: 50}, (_, slot) => Core.windowLight(ID, 0, slot));
  const floorB = Array.from({length: 50}, (_, slot) => Core.windowLight(ID, 1, slot));
  const anotherSource = Array.from({length: 50}, (_, slot) => Core.windowLight('osm/way/43', 0, slot));
  assert.notDeepEqual(floorA, floorB);
  assert.notDeepEqual(floorA, anotherSource);
});

test('window lights use bounded emissive markers only when lit, with about 55 percent occupancy', () => {
  let lit = 0, total = 0;
  const families = new Set();
  for (let source = 0; source < 80; source++) {
    for (let row = 0; row < 6; row++) for (let slot = -10; slot < 10; slot++) {
      const light = Core.windowLight('osm/way/' + source, row, slot);
      total++;
      assert.ok(light.colour.every(channel => Number.isFinite(channel) && channel >= 0 && channel <= 1.9));
      if (light.lit) {
        lit++;
        families.add(light.accentFamily);
        assert.ok(Math.max(...light.colour) > 1.25);
        assert.notEqual(light.accentFamily, 'off');
      } else {
        assert.deepEqual(light.colour, [0.035, 0.06, 0.085]);
        assert.equal(light.accentFamily, 'off');
        assert.ok(Math.max(...light.colour) < 1.25);
      }
    }
  }
  assert.ok(lit / total > 0.52 && lit / total < 0.58, `Lit occupancy: ${lit}/${total}`);
  assert.deepEqual([...families].sort(), ['amber', 'cyan', 'magenta']);
});

test('window lights reject invalid row/slot identities and returned colours cannot mutate their palette', () => {
  for (const [row, slot] of [[-1, 0], [0.5, 1], [NaN, 0], [0, Infinity], [0, 0.5], [0, '1']]) {
    assert.throws(() => Core.windowLight(ID, row, slot), TypeError);
  }
  const original = Core.windowLight(ID, 0, -2);
  const mutable = Core.windowLight(ID, 0, -2);
  mutable.colour[0] = 999;
  assert.deepEqual(Core.windowLight(ID, 0, -2), original);
});
