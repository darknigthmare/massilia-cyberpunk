#!/usr/bin/env node
'use strict';

// Derived from immutable game/tests/v74/browser_features.cjs.
// Parent SHA256: 6881cf87ec5e3aafa72590128804d4c3902fec76431f392269f27f785080318e; v75 executes its own built pages.
const { sourceEvidence, finishEvidence } = require('./browser_provenance.cjs');

// Real-page feature checks. Native zone/camera repositioning is explicit QA
// instrumentation; no entity, asset, network response or production API is mocked.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const argv = process.argv.slice(2), opts = { url: 'http://127.0.0.1:8777/SOMA_MASSILIA_URBAIN_v0_75.html', chromium: '/usr/bin/chromium', output: '/tmp/massilia-v75-features', timeout: 90000 };
for (let i = 0; i < argv.length; i++) {
  const key = argv[i].replace(/^--/, '');
  assert(Object.hasOwn(opts, key) && argv[i + 1], 'Unknown or incomplete option: ' + argv[i]);
  opts[key] = key === 'timeout' ? Number(argv[++i]) : argv[++i];
}
const report = { schema: 'soma/browser-features/75/1', startedAt: new Date().toISOString(), passed: false,
  environment: { freshContext: true, softwareWebGL: true, playwright: require('playwright/package.json').version },
  instrumentation: ['Native enterZone() and camera poses select existing authored units; this is not evidence of physical traversal.',
    'A native augmentation tick(0) settles the instrumented zone transition before the real scan keypress, without advancing its clocks.',
    'The real Maj+F2 handler activates Écho. Read-only snapshots and maintain()/scanTargets() exercise its installed presentation.',
    'The existing largeText setting is enabled through state.settings and applySettings() before marker screenshots.',
    'Native viewer teleportMetric() and mouse-drag input aim the existing rendered roofs for the real inspector.',
    'Real metropolitan NAV assets are read through the viewer scene lease. A corridor guide is not a mandatory route waypoint.'],
  limits: ['Authored combat-zone observation does not validate combat on NGF terrain; NGF body-altitude semantics require the separate sight61 fixture tests.',
    'Screenshots and native rendered geometry do not certify architectural 1:1 accuracy, complete metropolitan coverage or physical route traversal.',
    'No GPU or frame-time performance certification.'], steps: [], screenshots: [], pageErrors: [], consoleErrors: [], httpErrors: [] };
let browser, context, page, viewerBaseline;
const output = path.resolve(opts.output);
async function shot(name) { await page.screenshot({ path: path.join(output, name + '.png') }); report.screenshots.push(name + '.png'); }
async function step(name, run) {
  const row = { name, startedAt: new Date().toISOString() }; report.steps.push(row); process.stderr.write('[v75 features] ' + name + '\n');
  try { row.observation = await run(); row.status = 'passed'; return row.observation; }
  catch (e) { row.status = 'failed'; row.error = String(e.stack || e); throw e; }
  finally { row.finishedAt = new Date().toISOString(); }
}
function visibleBoxes(selector) {
  return Array.from(document.querySelectorAll(selector)).flatMap(node => {
    const s = getComputedStyle(node), r = node.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || r.width === 0 || r.height === 0) return [];
    return [{ id: node.id || node.className, text: node.textContent.trim().slice(0, 150), left: r.left, top: r.top, right: r.right, bottom: r.bottom }];
  });
}
function inViewport(box, viewport) { return box.left >= -1 && box.top >= -1 && box.right <= viewport.width + 1 && box.bottom <= viewport.height + 1; }
function overlap(a, b) { return Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2; }

async function main() {
  await fs.mkdir(output, { recursive: true });
  report.provenance = await sourceEvidence(__filename);
  try {
    browser = await chromium.launch({ executablePath: opts.chromium, headless: true, args: ['--no-sandbox', '--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    report.environment.chromium = browser.version();
    context = await browser.newContext({ viewport: { width: 1280, height: 720 }, locale: 'fr-FR' });
    page = await context.newPage(); page.setDefaultTimeout(opts.timeout);
    page.on('pageerror', error => report.pageErrors.push(String(error.stack || error)));
    page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push({ text: message.text(), location: message.location() }); });
    page.on('response', response => { if (response.status() >= 400) report.httpErrors.push({ url: response.url(), status: response.status() }); });

    await step('real-campaign-and-parent-hud', async () => {
      assert.equal((await page.goto(opts.url, { waitUntil: 'domcontentloaded' })).status(), 200);
      await page.waitForFunction(() => window.__SOMA_V75__?.ready && window.__SOMA_V73__?.ready && window.__SOMA_TACTICAL73__ && window.__SOMA_HUD72__?.ready);
      await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click();
      await page.waitForFunction(() => zone?.v52District && !paused);
      return page.evaluate(() => ({ edition: window.__SOMA_V75__.snapshot(), hud: window.__SOMA_HUD72__.snapshot(), zone: zone.id }));
    });
    for (const viewport of [{ width: 1024, height: 768 }, { width: 1280, height: 720 }]) {
      await step('hud-and-cortex-' + viewport.width + 'x' + viewport.height, async () => {
        await page.setViewportSize(viewport);
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const hud = await page.evaluate(visibleBoxes, '#v72-hud-layout [data-v72-hud]');
        assert(hud.length > 10, 'Actual v72 HUD roots must remain mounted.');
        assert.deepEqual(hud.filter(b => !inViewport(b, viewport)), [], 'Critical HUD root outside viewport.');
        await shot('hud-' + viewport.width + 'x' + viewport.height);
        await page.keyboard.press('Shift+F1');
        await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
        await page.locator('#v70-tactics .panel').evaluate(node => { node.scrollTop = 0; });
        const panel = await page.locator('#v70-tactics .panel').evaluate(node => ({ clientHeight: node.clientHeight, scrollHeight: node.scrollHeight, top: node.getBoundingClientRect().top, bottom: node.getBoundingClientRect().bottom, overflowY: getComputedStyle(node).overflowY }));
        assert(panel.top >= 0 && panel.bottom <= viewport.height + 1, 'Cortex scroll panel must fit the viewport.');
        await shot('cortex-' + viewport.width + 'x' + viewport.height);
        await page.locator('#v70-tactics [data-v70-close]').scrollIntoViewIfNeeded();
        const controls = await page.locator('#v70-tactics [data-v70-close]').boundingBox();
        assert(controls && controls.y >= 0 && controls.y + controls.height <= viewport.height + 1, 'Cortex close control must remain reachable.');
        assert.equal(await page.locator('#v72-hud-layout').evaluate(node => getComputedStyle(node).visibility), 'hidden');
        await shot('cortex-close-' + viewport.width + 'x' + viewport.height);
        await page.locator('#v70-tactics [data-v70-close]').click();
        await page.waitForFunction(() => !paused);
        return { viewport, roots: hud, cortexPanel: panel, cortexClose: controls, parentHudHiddenDuringMenu: true };
      });
    }

    await step('echo-real-units-fov-and-los', async () => {
      const fixture = await page.evaluate(() => {
        const candidates = Object.values(WORLD.zones).filter(z => !z.v52District && z.robots?.some(q => q.v32Enemy && q.health > 0));
        const preferred = WORLD.zones['v32-red-station'] || candidates[0];
        if (!preferred || !enterZone(preferred.id)) throw Error('No existing authored combat zone.');
        closeModals();
        window.__SOMA_V70__.tick(0);
        // Keep actual authored units. Select a legal floor pose via safePosition().
        const units = zone.robots.filter(q => q.health > 0 && !q.hidden);
        let clear = null, blocked = null;
        for (const q of units) for (const distance of [8, 12, 18, 22]) for (let i = 0; i < 24; i++) {
          const angle = i * Math.PI / 12, p = safePosition(zone, { x: q.x + Math.sin(angle) * distance, z: q.z + Math.cos(angle) * distance, yaw: 0 });
          const d = Math.hypot(q.x - p.x, q.z - p.z);
          if (d < 5 || d > 23) continue;
          const pose = { x: p.x, z: p.z, y: 1.72, yaw: Math.atan2(q.x - p.x, q.z - p.z), pitch: Math.atan2((q.v32Role === 'drone' ? 1.3 : q.v32Role === 'turret' ? 1.15 : 1.45) - 1.72, d) };
          if (lineBlocked(p.x, p.z, q.x, q.z)) blocked ||= { id: String(q.id), pose };
          else {
            const count = units.filter(other => {
              const d = Math.hypot(other.x - pose.x, other.z - pose.z), angle = Math.atan2(other.x - pose.x, other.z - pose.z) - pose.yaw;
              return d > 1 && d < 24 && Math.abs(Math.atan2(Math.sin(angle), Math.cos(angle))) < .7 && !lineBlocked(pose.x, pose.z, other.x, other.z);
            }).length;
            if (!clear || count > clear.count) clear = { id: String(q.id), pose, count };
          }
        }
        if (!clear || !blocked) throw Error('Native scene lacks both clear and wall-blocked floor poses.');
        Object.assign(camera, clear.pose); state.settings.largeText = true; applySettings(); paused = false;
        return { zone: zone.id, units: units.length, clear, blocked, before: window.__SOMA_V70__.snapshot(), sightNGFActive: window.__SOMA_SIGHT61__.activeFor(zone) };
      });
      await page.keyboard.press('Shift+F2');
      await page.waitForFunction(id => window.__SOMA_TACTICAL73__.snapshot().targets.some(q => q.id === id), fixture.clear.id);
      const results = await page.evaluate(({ clear, blocked }) => {
        const T = window.__SOMA_TACTICAL73__;
        const acquired = T.snapshot(), owner = window.__SOMA_V70__.snapshot();
        camera.yaw += Math.PI; T.maintain(); const behind = T.snapshot();
        Object.assign(camera, blocked.pose); T.scanTargets(); T.maintain(); const wall = T.snapshot();
        Object.assign(camera, clear.pose); T.scanTargets(); T.maintain(); const restored = T.snapshot();
        return { acquired, owner, behind, wall, restored, blockedByActualWall: lineBlocked(blocked.pose.x, blocked.pose.z, zone.robots.find(q => String(q.id) === blocked.id).x, zone.robots.find(q => String(q.id) === blocked.id).z) };
      }, fixture);
      assert.equal(results.owner.persisted.stats.scan, fixture.before.persisted.stats.scan + 1);
      assert.equal(results.owner.persisted.stats.activations, fixture.before.persisted.stats.activations + 1);
      assert(results.owner.active.scan > 0 && results.owner.persisted.cooldowns.scan > 0);
      assert(!results.behind.targets.some(q => q.id === fixture.clear.id), 'Unit behind the actual camera must disappear immediately.');
      assert(results.blockedByActualWall && !results.wall.targets.some(q => q.id === fixture.blocked.id), 'Native wall must block the inspected unit.');
      assert(results.restored.targets.some(q => q.id === fixture.clear.id));
      const layouts = [];
      for (const viewport of [{ width: 1024, height: 768 }, { width: 1280, height: 720 }]) {
        await page.setViewportSize(viewport);
        await page.evaluate(() => window.__SOMA_TACTICAL73__.maintain());
        const boxes = await page.evaluate(visibleBoxes, '.v73-tactical-marker');
        assert(boxes.length > 0 && boxes.length <= 4);
        assert.deepEqual(boxes.filter(b => !inViewport(b, viewport)), []);
        for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) assert(!overlap(boxes[i], boxes[j]), 'Markers overlap.');
        const hud = await page.evaluate(visibleBoxes, '#v72-hud-layout [data-v72-hud],#v73-tactical-hud');
        for (const box of boxes) assert(!hud.some(reserved => overlap(box, reserved)), 'Marker overlaps a parent HUD panel.');
        const critical = await page.evaluate(visibleBoxes, '.stats,#healthText,#armorText,#ammo');
        assert.equal(critical.length, 4, 'Health, armour, ammo and the vital panel must remain visible.');
        assert.deepEqual(critical.filter(b => !inViewport(b, viewport)), [], 'Critical combat HUD is clipped with large text.');
        layouts.push({ viewport, largeText: true, markers: boxes, hud, critical });
        await shot('echo-' + viewport.width + 'x' + viewport.height);
      }
      await page.keyboard.press('Shift+F1');
      await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
      const hiddenForMenu = await page.locator('#v73-tactical-markers').evaluate(node => getComputedStyle(node).display === 'none' || node.hidden);
      assert(hiddenForMenu, 'Écho markers must yield to the real Cortex menu.');
      await shot('echo-cortex-menu');
      await page.locator('#v70-tactics [data-v70-close]').click();
      await page.waitForFunction(() => !window.__SOMA_V70__.modifiers().scanActive, null, { timeout: 20000 });
      await page.evaluate(() => window.__SOMA_TACTICAL73__.maintain());
      assert.equal(await page.locator('#v73-tactical-markers').evaluate(node => node.hidden), true);
      return { fixture, results, layouts, hiddenForMenu, expiredMarkersHidden: true };
    });

    await step('real-viewer-corridor-guide-controls', async () => {
      await page.evaluate(() => { paused = true; });
      await page.goto(new URL('metropole-viewer-v75.html', opts.url).href, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => window.__SOMA_ROUTE70_VIEWER__ && window.__SOMA_METRO_VIEWER__?.snapshot().resident > 0);
      const before = await page.evaluate(() => Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)])));
      viewerBaseline = before;
      await page.locator('#route70-open').click();
      await page.waitForFunction(() => window.__SOMA_ROUTE70_VIEWER__.snapshot().phase === 'ready');
      const camera = await page.evaluate(() => window.__SOMA_METRO_VIEWER__.snapshot().camera);
      await page.locator('#route73-mark-guide').click();
      await page.waitForFunction(() => window.__SOMA_ROUTE70_VIEWER__.snapshot().phase === 'closed');
      const marked = await page.evaluate(() => window.__SOMA_ROUTE70_VIEWER__.snapshot().markers);
      assert.deepEqual(marked.corridorGuide, { e: camera.e, n: camera.n });
      assert.equal(marked.guideIsRouteWaypoint, false);
      await page.locator('#route70-open').click();
      await page.waitForFunction(() => window.__SOMA_ROUTE70_VIEWER__.snapshot().phase === 'ready');
      await page.locator('#route70-guide-e').fill('894487.9492004478');
      await page.locator('#route70-guide-n').fill('6249876.303378871');
      const manual = await page.evaluate(() => window.__SOMA_ROUTE70_VIEWER__.snapshot().markers);
      assert.deepEqual(manual.corridorGuide, { e: 894487.9492004478, n: 6249876.303378871 });
      await shot('route-guide-controls');
      await page.locator('#route73-clear-guide').click();
      const cleared = await page.evaluate(() => window.__SOMA_ROUTE70_VIEWER__.snapshot().markers);
      assert.equal(cleared.corridorGuide, null);
      assert.deepEqual(await page.evaluate(() => Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)]))), before);
      return { camera, marked, manual, cleared, exactStorageUnchanged: true };
    });

    await step('real-nav-guided-detour-7342m', async () => {
      const request = { start: { e: 892990.7467568527, n: 6247192.082113549 }, end: { e: 892985.1532743336, n: 6252557.397066671 }, endAxisKey: '["182028210",2,0,1]', maxAxisDistanceM: .01, mode: 'foot', corridorStage: 1 };
      const result = await page.evaluate(async request => {
        const R = window.__SOMA_ROUTE70_VIEWER__;
        const direct = await R.compute(request);
        const guided = await R.compute({ ...request, corridorGuide: { e: 894487.9492004478, n: 6249876.303378871 } });
        return { direct, guided, controller: R.snapshot(), scene: window.__SOMA_METRO_VIEWER__.snapshot() };
      }, request);
      assert.equal(result.direct.code, 'no_route_in_loaded_network');
      assert.equal(result.guided.status, 'route', JSON.stringify(result.guided));
      assert(result.guided.route.lengthMeters > 7000 && result.guided.route.lengthMeters < 7800);
      assert.equal(result.guided.coverage.corridorShape, 'guided_polyline');
      assert.equal(result.guided.coverage.guideIsRouteWaypoint, false);
      assert.equal(result.guided.physicalAccessibilityVerified, false);
      assert.equal(result.guided.physicalMovementReady, false);
      assert.equal(result.guided.campaignRoutingActivated, false);
      assert(result.guided.coverage.selectedCells.length <= 192 && result.guided.resources.nodes <= 48000 && result.guided.resources.edges <= 64000);
      assert.equal(result.controller.maximumConcurrentReads, 1);
      assert.equal(result.controller.inFlight, 0);
      await shot('route-guided-real-7342m');
      await fs.writeFile(path.join(output, 'guided-real-route.json'), JSON.stringify(result, null, 2) + '\n');
      await page.locator('#route70-close').click();
      await page.waitForFunction(() => window.__SOMA_ROUTE70_VIEWER__.snapshot().phase === 'closed');
      const drained = await page.evaluate(() => window.__SOMA_ROUTE70_VIEWER__.snapshot());
      assert.equal(drained.inFlight, 0);
      return { request, direct: { code: result.direct.code, coverage: result.direct.coverage }, guided: { status: result.guided.status, lengthMeters: result.guided.route.lengthMeters, coverage: result.guided.coverage, resources: result.guided.resources }, controller: result.controller, drained, detail: 'guided-real-route.json' };
    });
    for (const target of [
      { id: 'osm/way/264740443', e: 892399.566005424, n: 6247016.769814918, shape: 'hipped', pose: { e: 892396.7528025161, n: 6247009.063011345, h: 140 } },
      { id: 'osm/way/264740444', e: 892410.5834039208, n: 6247018.6796232555, shape: 'gabled', pose: { e: 892407.7699730197, n: 6247010.9721950935, h: 140 } },
    ]) {
      await step('rendered-source-roof-' + target.shape, async () => {
        const moved = await page.evaluate(target => window.__SOMA_METRO_VIEWER__.teleportMetric(target.pose.e, target.pose.n, target.pose.h), target);
        assert(moved);
        await page.waitForFunction(() => { const s = window.__SOMA_METRO_VIEWER__.snapshot(); return s.pendingGeometry === 0 && s.buildings > 0; });
        // These poses were found against actual rendered source triangles with
        // Arch71.pickScene(), including the real building-part omissions.
        // The native drag handler aims the ordinary inspector ray; no occluding
        // geometry or hit is removed or replaced.
        await page.locator('#scene').dispatchEvent('mousedown');
        await page.evaluate(() => window.dispatchEvent(new MouseEvent('mousemove', { movementX: (.35 - window.__SOMA_METRO_VIEWER__.snapshot().camera.yaw) / .002, movementY: 475, bubbles: true })));
        await page.evaluate(() => window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })));
        const camera = await page.evaluate(() => window.__SOMA_METRO_VIEWER__.snapshot().camera);
        assert(Math.abs(camera.pitch + 1.5) < 1e-6);
        await shot('roof-' + target.shape + '-rendered');
        await page.locator('#architecture71-open').click();
        await page.waitForFunction(() => window.__SOMA_ARCHITECTURE71_VIEWER__.snapshot().phase === 'ready');
        const result = await page.evaluate(() => window.__SOMA_ARCHITECTURE71_VIEWER__.snapshot().result);
        assert.equal(result.status, 'building', JSON.stringify(result));
        assert(result.testedTriangles > 0, 'Inspector must test the real streamed triangles.');
        assert.equal(result.selection.id, target.id);
        assert.equal(result.selection.roof.displayedShape, target.shape);
        assert.equal(result.selection.roof.reason, 'osm-parametric-' + target.shape + '-source-clipped-frame');
        assert.equal(result.selection.roof.surveyed, false);
        assert.equal(result.selection.architecturalOneToOneCertified, false);
        assert.equal(result.selection.physicalAccessVerified, false);
        const foundation = result.selection.datum74;
        assert(foundation, 'The selected source roof must retain the reviewed foundation evidence.');
        assert.equal(foundation.parentId, 'osm/way/264740428');
        assert.equal(foundation.supportId, 'osm/way/264740436');
        assert.equal(foundation.osmRelation, false);
        assert.equal(foundation.association, 'derived-source-boundary-containment');
        assert.equal(foundation.boundaryToleranceMeters, .01);
        assert.equal(foundation.surveyed, false);
        assert.equal(foundation.sourcePbfSHA256, result.selection.footprint.sourcePbfSHA256);
        assert.equal(foundation.geometrySHA256, result.selection.footprint.geometrySHA256);
        assert.equal(foundation.baseAltitudeNGFMeters, result.selection.baseAltitudeNGFMeters);
        assert(foundation.baseAltitudeNGFMeters >= foundation.beforeBaseAltitudeNGFMeters);
        assert(result.selection.hitL93.h > foundation.baseAltitudeNGFMeters + 20 &&
          result.selection.hitL93.h <= foundation.baseAltitudeNGFMeters + 23.01,
        'Actual hit triangle must lie in the declared roof height interval above its common foundation.');
        assert.match(await page.locator('#architecture71-facts').innerText(), /Fondation commune interprétée/);
        await shot('roof-' + target.shape + '-inspector');
        await page.locator('#architecture71-close').click();
        await page.waitForFunction(() => window.__SOMA_ARCHITECTURE71_VIEWER__.snapshot().phase === 'closed');
        return { target, camera, result, foundationRuntime: await page.evaluate(() => window.__SOMA_ARCHITECTURE74__.snapshot()),
          scope: 'Real streamed triangles, source-clipped roof, common interpreted foundation and inspector evidence; no surveyed-roof or physical-access claim.' };
      });
    }
    await step('viewer-errors-storage-and-release', async () => {
      const result = await page.evaluate(() => ({ scene: window.__SOMA_METRO_VIEWER__.snapshot(), route: window.__SOMA_ROUTE70_VIEWER__.snapshot(), inspector: window.__SOMA_ARCHITECTURE71_VIEWER__.snapshot(), storage: Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)])) }));
      assert.equal(result.scene.buildFailures, 0);
      assert.deepEqual(result.scene.errors, []);
      assert.deepEqual(result.scene.webglErrors, []);
      assert.equal(result.route.phase, 'closed');
      assert.equal(result.route.inFlight, 0);
      assert.equal(result.inspector.phase, 'closed');
      assert.deepEqual(result.storage, viewerBaseline);
      return { scene: result.scene, route: result.route, inspector: result.inspector, exactCampaignStorageUnchanged: true };
    });
    assert.deepEqual(report.pageErrors, []);
    assert.deepEqual(report.httpErrors, []);
    assert.deepEqual(report.consoleErrors, []);
    report.passed = true;
  } catch (error) {
    report.failure = String(error.stack || error);
    try { if (page) await shot('failure'); } catch (e) { report.screenshotFailure = String(e); }
    process.exitCode = 1;
  } finally {
    await browser?.close();
    await finishEvidence(report, __filename);
    report.finishedAt = new Date().toISOString();
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    process.stdout.write(JSON.stringify({ passed: report.passed, report: path.join(output, 'report.json'), steps: report.steps.map(({ name, status }) => ({ name, status })), failure: report.failure }, null, 2) + '\n');
  }
}
main().catch(error => { process.stderr.write(String(error.stack || error)); process.exitCode = 1; });
