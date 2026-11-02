#!/usr/bin/env node
'use strict';

// Native data integration: all grid, geometry, contact, sight and persistence
// owners stay installed. Only native scene-entry/camera setup is instrumented.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { sourceEvidence, finishEvidence } = require('./browser_provenance.cjs');
const opts = { url: 'http://127.0.0.1:8777/SOMA_MASSILIA_URBAIN_v0_75.html', chromium: '/usr/bin/chromium', output: '/tmp/massilia-v75-terrain', timeout: 90000 };
for (let i = 2; i < process.argv.length; i++) {
  const key = process.argv[i].replace(/^--/, '');
  assert(Object.hasOwn(opts, key) && process.argv[i + 1], 'Unknown or incomplete option.');
  opts[key] = key === 'timeout' ? Number(process.argv[++i]) : process.argv[++i];
}
const output = path.resolve(opts.output), nativeSHA = '369b81cbdadecbe6e6c96bd849559a6707aaa7106bb702949509474e92b245c0';
const report = { schema: 'soma/browser-terrain/75/1', passed: false, startedAt: new Date().toISOString(),
  environment: { freshNonPersistentContext: true, softwareWebGLRequested: true, viewport: { width: 1280, height: 720 } },
  instrumentation: [
    'Native enterZone()/v54.enter() select existing historical and source cells; this does not prove travel between them.',
    'The ordinary Atlas button installs the delivered 5 m pack through terrain56/58. No grid, mask, source response or renderer is replaced.',
    'Grid triangles, generated static mesh and renderer composition are hashed from their real installed arrays.',
    'A downward ray from 10 m above actual ground exercises sight61 terrain occlusion with other real occluder classes explicitly disabled for isolation.',
  ], limits: [
    'This bounded native cell scenario does not prove all 168 cells physically traversable, step accessibility, complete human campaign, metropolitan coverage or architectural 1:1 fidelity.',
    'SwiftShader execution does not measure player GPU performance.',
  ], steps: [], screenshots: [], pageErrors: [], consoleErrors: [], consoleWarnings: [], httpErrors: [], requestFailures: [] };
let browser, context, page, currentStep = 'launch', baseline, native, exported;
const spatialCases = [
  { name: 'port', cellId: 'V52-MC-W05-S01', sourceWay: 'osm/way/549015590', x: 52.193464753218, z: 41.874879509211, yaw: 2.169450126296119, pitch: -.12, nativeGroundNGF: 2.670015535484, legacyGroundNGF: 10.626059510919 },
  { name: 'slope-fort', cellId: 'V52-MC-W05-S02', sourceWay: 'osm/way/343960949', x: 110.571616416099, z: -92.234601588920, yaw: .6129919211695444, pitch: -.12, nativeGroundNGF: 22.497358114681, legacyGroundNGF: 8.445410869804 },
];
const spatialBaseline = {};
async function step(name, run) {
  currentStep = name; const row = { name, startedAt: new Date().toISOString() }; report.steps.push(row);
  process.stderr.write('[v75 terrain] ' + name + '\n');
  try { row.observation = await run(); row.status = 'passed'; return row.observation; }
  catch (error) { row.status = 'failed'; row.error = String(error.stack || error); throw error; }
  finally { row.finishedAt = new Date().toISOString(); }
}
async function shot(name) {
  // The fixture pauses after direct native entry/move calls; settle the actual
  // terrain HUD owner synchronously before capturing its current altitude.
  await page.evaluate(() => window.__SOMA_TERRAIN56__?.refresh());
  await page.screenshot({ path: path.join(output, name + '.png') }); report.screenshots.push(name + '.png');
}
async function ready() { await page.waitForFunction(() => window.__SOMA_V75__?.ready && window.__SOMA_TERRAIN75__?.ready && window.__SOMA_SIGHT61__?.ready && window.__SOMA_GROUP64__?.ready); }
async function evidence(fixture = null) {
  return page.evaluate(async fixture => {
    const T = window.__SOMA_TERRAIN56__, G = T.grid, H = window.__SOMA_TERRAIN75__;
    const digest = async value => {
      const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value instanceof Float32Array ? new Uint8Array(value.buffer, value.byteOffset, value.byteLength) : new Uint8Array(new Float32Array(value).buffer);
      return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2, '0')).join('');
    };
    const triangles = [], counts = G.cellTriangles(zone.v50Record.boundsL93, t => triangles.push(...t.flat()));
    const bounds = zone.v50Record.boundsL93, centreSampleNGF = G.sample((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2);
    const ground = T.ground(zone, camera.x, camera.z), rayOriginNGF = fixture ? fixture.nativeGroundNGF + 10 : ground + 10;
    const terrainRay = window.__SOMA_SIGHT61__.trace([camera.x, rayOriginNGF, camera.z], [0, -1, 0], 100, zone, { terrain: true, buildings: false, vehicles: false, extras: false });
    window.__SOMA_V54__.refreshScene();
    return { zone: zone.id, grid: T.snapshot().grid, terrain: H.snapshot(), build: { ...zone.v56Build }, counts,
      triangleSHA256: await digest(triangles), staticMeshSHA256: await digest(zone.static), centreSampleNGF,
      rendererCompositionSHA256: renderer.__v65Static ? await digest(renderer.__v65Static) : null,
      vectorRecordSHA256: await digest(JSON.stringify(zone.v50Record)),
      ground, terrainRay, rayOriginNGF, slope: T.slope(zone, camera.x, camera.z), camera: { x: camera.x, y: camera.y, z: camera.z, yaw: camera.yaw, pitch: camera.pitch },
      blocked: blocked(zone, camera.x, camera.z, .38), webgl2: renderer.gl instanceof WebGL2RenderingContext,
      linked: renderer.gl.getProgramParameter(renderer.p, renderer.gl.LINK_STATUS), lost: renderer.gl.isContextLost() };
  }, fixture);
}
async function enterSource() {
  assert(await page.evaluate(() => window.__SOMA_V54__.enter('V52-MC-11')));
  await page.waitForFunction(() => zone?.id === 'geo:V52-MC-11' && zone.static && window.__SOMA_TERRAIN56__.activeFor(zone));
  await page.evaluate(() => { closeModals(); paused = true; window.__SOMA_TERRAIN56__.poseCamera(); });
}
async function enterSpatial(fixture) {
  const entry = await page.evaluate(f => {
    const started = performance.now();
    if (!enterZone('geo:' + f.cellId, null, { x: f.x, z: f.z, yaw: f.yaw, pitch: f.pitch })) throw Error('Native source-cell entry refused: ' + f.cellId);
    closeModals(); paused = true; window.__SOMA_TERRAIN56__.poseCamera();
    return { entryWallMs: performance.now() - started, x: camera.x, z: camera.z, blocked: blocked(zone, camera.x, camera.z, .38), sourceWayPresent: zone.v50Record.featureCollection.features.some(feature => (feature.properties?.canonical_id || feature.id) === f.sourceWay) };
  }, fixture);
  assert(!entry.blocked && entry.sourceWayPresent, 'Candidate must be a real source way on free native floor.');
  assert(Math.hypot(entry.x - fixture.x, entry.z - fixture.z) < 1e-6, 'Native entry must preserve the qualified source pose.');
  return entry;
}
async function main() {
  await fs.mkdir(output, { recursive: true });
  report.provenance = await sourceEvidence(__filename);
  try {
    browser = await chromium.launch({ executablePath: opts.chromium, headless: true, args: ['--no-sandbox', '--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    report.environment.chromium = browser.version(); report.environment.playwright = require('playwright/package.json').version;
    context = await browser.newContext({ viewport: report.environment.viewport, locale: 'fr-FR' });
    assert.deepEqual((await context.storageState()).origins, []);
    page = await context.newPage(); page.setDefaultTimeout(opts.timeout);
    page.on('pageerror', error => report.pageErrors.push({ step: currentStep, error: String(error.stack || error) }));
    page.on('console', message => { const row = { step: currentStep, text: message.text(), location: message.location() }; if (message.type() === 'error') report.consoleErrors.push(row); if (message.type() === 'warning') report.consoleWarnings.push(row); });
    page.on('response', response => { if (response.status() >= 400) report.httpErrors.push({ step: currentStep, status: response.status(), url: response.url() }); });
    page.on('requestfailed', request => report.requestFailures.push({ step: currentStep, url: request.url(), error: request.failure()?.errorText }));
    await step('fresh-profile-preserves-historical25m-default', async () => {
      assert.equal((await page.goto(opts.url, { waitUntil: 'domcontentloaded' })).status(), 200); await ready();
      const initial = await page.evaluate(() => window.__SOMA_TERRAIN75__.snapshot());
      assert.equal(initial.selected, 'legacy25m'); assert.equal(initial.stepM, 25); assert.equal(initial.active, false);
      await enterSource(); baseline = await evidence();
      assert.equal(baseline.grid.stepM, 25); assert.equal(baseline.counts.triangles, 200);
      await shot('01-historical25m-source-cell'); return { initial, baseline };
    });
    await step('source-port-and-slope-baselines-on-historical25m', async () => {
      const observations = [];
      for (const fixture of spatialCases) {
        const entry = await enterSpatial(fixture), observed = await evidence(fixture);
        assert(Math.abs(observed.ground - fixture.legacyGroundNGF) < 1e-6);
        assert.equal(observed.terrainRay.kind, 'terrain'); assert(Math.abs(observed.terrainRay.point[1] - observed.ground) < 1e-5);
        spatialBaseline[fixture.name] = observed; await shot('baseline25m-' + fixture.name);
        observations.push({ fixture, entry, observed });
      }
      return observations;
    });
    await step('ordinary-atlas-button-installs-native5m-owner', async () => {
      await page.evaluate(() => { closeModals(); if (!enterZone('station-exterior')) throw Error('Historical scene entry refused.'); window.__SOMA_V52__.open(); });
      const button = page.locator('[data-terrain75-native]'); await button.scrollIntoViewIfNeeded();
      assert(await button.isEnabled()); await button.click();
      await page.waitForFunction(() => window.__SOMA_TERRAIN75__.active() && !window.__SOMA_TERRAIN75__.snapshot().busy);
      const installed = await page.evaluate(() => window.__SOMA_TERRAIN75__.snapshot());
      assert.equal(installed.gridSHA256, nativeSHA); assert.equal(installed.stepM, 5); assert.equal(installed.sessionOnly, false);
      assert.equal(installed.newGeographicCells, 0); assert.equal(installed.campaignCells, 168); assert.equal(installed.certified, false);
      assert.equal(await button.getAttribute('aria-pressed'), 'true'); await shot('02-native5m-atlas-owner'); return installed;
    });
    await step('native-grid-renders-contact-and-occlusion-from-same-source', async () => {
      await enterSource(); native = await evidence();
      assert.equal(native.grid.stepM, 5); assert.equal(native.grid.cols, 653); assert.equal(native.grid.rows, 653);
      assert.equal(native.grid.statistics.valid, 424059); assert.equal(native.grid.statistics.noData, 2350);
      assert.equal(native.build.terrainSHA256, nativeSHA); assert.equal(native.build.stepM, 5);
      assert.equal(native.counts.triangles, 5000); assert.equal(native.counts.missing, 0); assert.equal(native.build.triangles, native.counts.triangles);
      assert.equal(native.centreSampleNGF, 14.500489234924316); assert.equal(baseline.centreSampleNGF, 14.449999809265137);
      assert.equal(native.vectorRecordSHA256, baseline.vectorRecordSHA256);
      assert.notEqual(native.triangleSHA256, baseline.triangleSHA256); assert.notEqual(native.staticMeshSHA256, baseline.staticMeshSHA256);
      assert.notEqual(native.rendererCompositionSHA256, baseline.rendererCompositionSHA256);
      assert(native.webgl2 && native.linked && !native.lost && !native.blocked);
      assert(Math.abs(native.camera.y - native.ground - 1.72) < 1e-6);
      const sight = await page.evaluate(() => {
        const T = window.__SOMA_TERRAIN56__, S = window.__SOMA_SIGHT61__, h = T.ground(zone, camera.x, camera.z);
        const hit = S.trace([camera.x, h + 10, camera.z], [0, -1, 0], 20, zone, { terrain: true, buildings: false, vehicles: false, extras: false });
        return { hit, ground: h, active: S.activeFor(zone), snapshot: S.summary() };
      });
      assert(sight.active); assert.equal(sight.hit.kind, 'terrain'); assert(Math.abs(sight.hit.distance - 10) < 1e-5); assert(Math.abs(sight.hit.point[1] - sight.ground) < 1e-5);
      await shot('03-native5m-rendered-contact'); return { native, sight };
    });
    await step('native5m-port-and-slope-change-real-surfaces-and-occlusion', async () => {
      const observations = [];
      for (const fixture of spatialCases) {
        const entry = await enterSpatial(fixture), observed = await evidence(fixture), previous = spatialBaseline[fixture.name];
        assert.equal(observed.build.terrainSHA256, nativeSHA); assert.equal(observed.build.triangles, 5000); assert.equal(observed.build.missing, 0);
        assert(Math.abs(observed.ground - fixture.nativeGroundNGF) < 1e-6); assert(Math.abs(observed.camera.y - observed.ground - 1.72) < 1e-6);
        assert(Math.abs(observed.ground - previous.ground) > 5, 'The extra source case must have a material measured elevation difference.');
        assert.equal(observed.vectorRecordSHA256, previous.vectorRecordSHA256); assert.notEqual(observed.staticMeshSHA256, previous.staticMeshSHA256); assert.notEqual(observed.triangleSHA256, previous.triangleSHA256);
        assert.equal(observed.terrainRay.kind, 'terrain'); assert(Math.abs(observed.terrainRay.distance - 10) < 1e-5); assert(Math.abs(observed.terrainRay.point[1] - observed.ground) < 1e-5);
        assert(Math.abs(observed.terrainRay.distance - previous.terrainRay.distance) > 5);
        if (fixture.name === 'slope-fort') assert(Math.hypot(observed.slope.e, observed.slope.south) > .2);
        await shot('native5m-' + fixture.name); observations.push({ fixture, entry, previous, observed });
      }
      return observations;
    });
    await step('native-source-road-seam55-walks-port-to-fort', async () => {
      const setup = await page.evaluate(() => {
        const id = 'geo:V52-MC-W05-S01', F = window.__SOMA_V55__, T = window.__SOMA_TERRAIN56__;
        if (!enterZone(id, null, { x: 121.964576751343, z: 123.8, yaw: 0, pitch: -.12 })) throw Error('Port approach entry refused.');
        closeModals(); paused = false; T.poseCamera();
        const neighbor = F.neighbor(zone, 'S'); if (neighbor?.id !== 'geo:V52-MC-W05-S02') throw Error('The actual source seam does not lead to the expected adjacent fort cell.');
        const portal = zone.portals.find(p => p.side === 'S' && p.target === neighbor.id && p.v53VerifiedSeam && String(p.v50SourceId).includes('120922878'));
        if (!portal) throw Error('No source-verified Avenue Vaudoyer portal at this real seam.');
        for (let i = 0; i <= 30; i++) {
          const z = 123.8 + i * .12, slope = T.slope(zone, camera.x, z);
          if (blocked(zone, camera.x, z, .38) || !Number.isFinite(T.ground(zone, camera.x, z)) || !slope || Math.hypot(slope.e, slope.south) > .95) throw Error('The source seam approach is not physically free/supported.');
        }
        return { zone: zone.id, x: camera.x, z: camera.z, ground: T.ground(zone, camera.x, camera.z), portal: { code: portal.code, side: portal.side, target: portal.target, sourceWay: portal.v50SourceId, verified: portal.v53VerifiedSeam }, before: F.progress().travel };
      });
      await page.keyboard.down('w'); let crossing;
      try {
        crossing = await page.evaluate(() => {
          const rows = [], T = window.__SOMA_TERRAIN56__;
          for (let i = 0; i < 20 && zone.id === 'geo:V52-MC-W05-S01'; i++) { move(.1); rows.push({ zone: zone.id, x: camera.x, y: camera.y, z: camera.z, ground: T.ground(zone, camera.x, camera.z), blocked: blocked(zone, camera.x, camera.z, .38) }); }
          paused = true; return { rows, zone: zone.id, terrain: window.__SOMA_TERRAIN75__.snapshot(), travel: window.__SOMA_V55__.progress().travel };
        });
      } finally { await page.keyboard.up('w'); }
      assert.equal(crossing.zone, 'geo:V52-MC-W05-S02'); assert.equal(crossing.terrain.gridSHA256, nativeSHA); assert(crossing.travel.footCrossings > setup.before.footCrossings);
      assert(crossing.rows.every(row => Number.isFinite(row.ground) && !row.blocked && Math.abs(row.y - row.ground - 1.72) < 1e-5));
      assert.equal(crossing.travel.lastCrossing.from, 'V52-MC-W05-S01'); assert.equal(crossing.travel.lastCrossing.to, 'V52-MC-W05-S02'); assert(crossing.travel.lastCrossing.errorMeters < 1e-6);
      await shot('native5m-source-road-seam55'); return { setup, crossing, limit: 'A short source-road seam crossing; no complete route or whole-cell accessibility claim.' };
    });
    await step('real-grouped-import-keeps-installed5m-and-owned-state', async () => {
      const before = await page.evaluate(() => ({ credits: state.credits, v70: JSON.parse(JSON.stringify(state.v70)), terrain: window.__SOMA_TERRAIN75__.snapshot(), zone: zone.id }));
      exported = await page.evaluate(() => window.__SOMA_GROUP64__.exportText());
      await fs.writeFile(path.join(output, 'native5m-grouped-save.json'), exported);
      const imported = await page.evaluate(text => window.__SOMA_GROUP64__.importText(text, true), exported); assert.equal(imported.ok, true);
      const after = await page.evaluate(() => { paused = true; return { credits: state.credits, v70: JSON.parse(JSON.stringify(state.v70)), terrain: window.__SOMA_TERRAIN75__.snapshot(), zone: zone.id, coreDomains: Object.keys(window.__SOMA_V37_SAVE__.snapshot().payload.core).filter(k => /^v7[1-5]$/.test(k)) }; });
      assert.equal(after.credits, before.credits); assert.deepEqual(after.v70, before.v70); assert.equal(after.zone, before.zone);
      assert.equal(after.terrain.gridSHA256, nativeSHA); assert.deepEqual(after.coreDomains, []); return { before, imported, after };
    });
    await step('reload-reconciles-existing-indexeddb5m-cache', async () => {
      await page.reload({ waitUntil: 'domcontentloaded' }); await ready();
      await page.waitForFunction(() => window.__SOMA_TERRAIN75__.active() && zone?.v52District && zone.static);
      await page.evaluate(() => { paused = true; window.__SOMA_TERRAIN56__.poseCamera(); });
      const restored = await evidence(); assert.equal(restored.terrain.gridSHA256, nativeSHA); assert.equal(restored.build.terrainSHA256, nativeSHA);
      assert.equal(restored.grid.stepM, 5); assert(!restored.blocked && Number.isFinite(restored.ground));
      assert(Math.abs(restored.camera.y - restored.ground - 1.72) < 1e-6); await shot('04-native5m-reloaded'); return restored;
    });
    await step('historical-relief-restores-through-same-atlas-owner', async () => {
      await page.evaluate(() => { closeModals(); enterZone('station-exterior'); window.__SOMA_V52__.open(); });
      await page.locator('[data-terrain75-legacy]').scrollIntoViewIfNeeded(); await page.locator('[data-terrain75-legacy]').click();
      await page.waitForFunction(() => window.__SOMA_TERRAIN75__.snapshot().selected === 'legacy25m' && !window.__SOMA_TERRAIN75__.snapshot().busy);
      const restored = await page.evaluate(() => window.__SOMA_TERRAIN75__.snapshot()); assert.equal(restored.stepM, 25); assert.equal(restored.active, false); return restored;
    });
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.httpErrors, []); assert.deepEqual(report.requestFailures, []); report.passed = true;
  } catch (error) { report.failure = String(error.stack || error); process.exitCode = 1; try { if (page) await shot('failure-' + currentStep); } catch (captureError) { report.captureFailure = String(captureError); } }
  finally {
    await browser?.close(); await finishEvidence(report, __filename); report.finishedAt = new Date().toISOString();
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    process.stdout.write(JSON.stringify({ passed: report.passed, report: path.join(output, 'report.json'), steps: report.steps.map(({ name, status }) => ({ name, status })), failure: report.failure }, null, 2) + '\n');
  }
}
main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
