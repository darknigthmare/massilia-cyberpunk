#!/usr/bin/env node
'use strict';

// Derived from frozen browser_mechanics74 SHA256 74860cc9ecb974f225eab9034f08a0e9524a356d86572ee55adf9f47608d860c.
// Bounded integration of the installed v20/v42/v56 movement and v32 combat
// owners. Native actors/vehicles are retained; setup mutations are reported.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { sourceEvidence, finishEvidence } = require('./browser_provenance.cjs');
const opts = { url: 'http://127.0.0.1:8777/SOMA_MASSILIA_URBAIN_v0_75.html', chromium: '/usr/bin/chromium', output: '/tmp/massilia-v75-mechanics', timeout: 90000 };
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const key = argv[i].replace(/^--/, '');
  assert(Object.hasOwn(opts, key) && argv[i + 1], 'Unknown or incomplete argument: ' + argv[i]);
  opts[key] = key === 'timeout' ? Number(argv[++i]) : argv[++i];
}
const output = path.resolve(opts.output);
const report = { schema: 'soma/browser-mechanics/75/1', passed: false, startedAt: new Date().toISOString(),
  environment: { freshNonPersistentContext: true, softwareWebGLRequested: true, viewport: { width: 1280, height: 720 } },
  instrumentation: [
    'A collision/terrain-checked initial pose is selected in the actual geographic scene; subsequent walking uses the installed controller and keyboard input.',
    'The existing enterVehicle/exitVehicle owners are called on an existing pilotable vehicle. No road, terrain, collider or vehicle is created.',
    'The native5m pack is installed by its owner before source-cell movement. Existing authored vehicle identity and actual source obstacles are retained.',
    'Vehicle frame trials call the installed stepVehicle owner synchronously at30/60/120Hz; the browser animation loop cannot interleave during one evaluate call. No ground/collision owner is replaced.',
  ],
  limits: [
    'Controlled initial poses and injuries are fixtures, not a campaign playthrough or naturally triggered combat encounter.',
    'Short local controller traces do not establish physical accessibility outside the tested scene or throughout the metropolitan viewer.',
    'SwiftShader screenshots do not certify player GPU performance or architectural 1:1 fidelity.',
  ], steps: [], screenshots: [], pageErrors: [], consoleErrors: [], httpErrors: [] };
let browser, context, page, currentStep = 'launch';
async function shot(name) { await page.screenshot({ path: path.join(output, name + '.png') }); report.screenshots.push(name + '.png'); }
async function step(name, run) {
  currentStep = name; const row = { name, startedAt: new Date().toISOString() }; report.steps.push(row);
  process.stderr.write('[v75 mechanics] ' + name + '\n');
  try { row.observation = await run(); row.status = 'passed'; return row.observation; }
  catch (error) { row.status = 'failed'; row.error = String(error.stack || error); throw error; }
  finally { row.finishedAt = new Date().toISOString(); }
}
function poseSnapshot() {
  const T = window.__SOMA_TERRAIN56__, v = zone.vehicles?.find(q => q.id === state.driving);
  return { zone: zone.id, camera: { x: camera.x, y: camera.y, z: camera.z, yaw: camera.yaw },
    ground: T.ground(zone, camera.x, camera.z), blocked: blocked(zone, camera.x, camera.z, .38),
    lastOnFoot: JSON.parse(JSON.stringify(state.lastOnFoot)), driving: state.driving,
    vehicle: v ? { id: v.id, x: v.x, z: v.z, speed: v.speed, condition: v.condition } : null,
    distanceDriven: state.statistics.distanceDriven || 0, mobility: window.__SOMA_MOBILITY74__.snapshot() };
}
async function main() {
  await fs.mkdir(output, { recursive: true });
  report.provenance = await sourceEvidence(__filename);
  try {
    browser = await chromium.launch({ executablePath: opts.chromium, headless: true,
      args: ['--no-sandbox', '--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    report.environment.chromium = browser.version(); report.environment.playwright = require('playwright/package.json').version;
    context = await browser.newContext({ viewport: report.environment.viewport, locale: 'fr-FR' });
    assert.deepEqual((await context.storageState()).origins, []);
    page = await context.newPage(); page.setDefaultTimeout(opts.timeout);
    page.on('pageerror', error => report.pageErrors.push({ step: currentStep, error: String(error.stack || error) }));
    page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push({ step: currentStep, text: message.text(), location: message.location() }); });
    page.on('response', response => { if (response.status() >= 400) report.httpErrors.push({ step: currentStep, status: response.status(), url: response.url() }); });
    await step('load-installed-v74-owners', async () => {
      assert.equal((await page.goto(opts.url, { waitUntil: 'domcontentloaded' })).status(), 200);
      await page.waitForFunction(() => window.__SOMA_V75__?.ready && window.__SOMA_MOBILITY74__?.ready && window.__SOMA_VEHICLES75__?.ready && window.__SOMA_TERRAIN75__?.ready && window.__SOMA_COMBAT75__);
      assert(await page.evaluate(() => window.__SOMA_TERRAIN75__.select('native5m')), 'Native5m must install outside the physical campaign.');
      await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click();
      await page.waitForFunction(() => zone?.v52District && !paused && window.__SOMA_TERRAIN56__.activeFor(zone));
      return page.evaluate(() => ({ edition: window.__SOMA_V75__.snapshot(), geographicZone: zone.id,
        buildings: zone.v68Architecture.buildings, mobility: window.__SOMA_MOBILITY74__.snapshot(), vehicles75: window.__SOMA_VEHICLES75__.snapshot(), terrain75: window.__SOMA_TERRAIN75__.snapshot(), combat75: window.__SOMA_COMBAT75__.snapshot() }));
    });
    await step('keyboard-grounded-street-trace', async () => {
      const setup = await page.evaluate(() => {
        const T = window.__SOMA_TERRAIN56__, candidates = [{ x: camera.x, z: camera.z }, ...(zone.roads || []).map(r => ({ x: r.x, z: r.z }))];
        let selected = null;
        for (const p of candidates) for (let a = 0; a < 16 && !selected; a++) {
          const yaw = a * Math.PI / 8, x = p.x - Math.sin(yaw) * 10, z = p.z - Math.cos(yaw) * 10;
          let previous = T.ground(zone, x, z), ok = Number.isFinite(previous);
          for (let i = 0; i <= 100 && ok; i++) {
            const px = x + Math.sin(yaw) * i * .2, pz = z + Math.cos(yaw) * i * .2;
            const h = T.ground(zone, px, pz), s = T.slope(zone, px, pz);
            ok = Math.abs(px) < 120 && Math.abs(pz) < 120 && Number.isFinite(h) && s && Math.hypot(s.e, s.south) < .65 &&
              Math.abs(h - previous) < .15 && !blocked(zone, px, pz, .38) && pedestrianVehicleClear(px, pz, null, .38);
            previous = h;
          }
          if (ok) selected = { x, z, yaw, lengthM: 20 };
        }
        if (!selected) throw Error('No source-terrain/collision-checked 20 m street trace in the initial cell.');
        Object.assign(camera, selected); T.poseCamera(); paused = false;
        return { selected, sourceZone: zone.id, terrain: T.snapshot?.() || null };
      });
      const before = await page.evaluate(poseSnapshot);
      await page.keyboard.down('Shift'); await page.keyboard.down('w');
      let trace;
      try {
        trace = await page.evaluate(async () => {
          const start = { x: camera.x, z: camera.z }, samples = [], started = performance.now();
          while (performance.now() - started < 25000) {
            await new Promise(resolve => setTimeout(resolve, 100));
            const h = window.__SOMA_TERRAIN56__.ground(zone, camera.x, camera.z);
            samples.push({ x: camera.x, y: camera.y, z: camera.z, ground: h, paused, driving: state.driving,
              blocked: blocked(zone, camera.x, camera.z, .38), lastOnFoot: { ...state.lastOnFoot } });
            if (Math.hypot(camera.x - start.x, camera.z - start.z) >= 17) break;
          }
          return { samples, wallMilliseconds: performance.now() - started, displacementM: Math.hypot(camera.x - start.x, camera.z - start.z) };
        });
      } finally { await page.keyboard.up('w'); await page.keyboard.up('Shift'); }
      const after = await page.evaluate(poseSnapshot);
      assert(trace.displacementM >= 15 && trace.displacementM < 23, JSON.stringify(trace));
      assert(trace.samples.every(p => Number.isFinite(p.ground) && Math.abs(p.y - p.ground - 1.72) < .08 && !p.blocked && !p.paused && !p.driving));
      assert(after.mobility.stats.footSubsteps > before.mobility.stats.footSubsteps);
      assert(Math.hypot(after.lastOnFoot.x - after.camera.x, after.lastOnFoot.z - after.camera.z) < .7);
      await shot('street-grounded-trace');
      return { setup, before, trace, after };
    });
    await step('geographic-source-obstacle-stops-controller', async () => {
      const setup = await page.evaluate(() => {
        const T = window.__SOMA_TERRAIN56__, points = [];
        for (const c of zone.colliders || []) {
          if (![c.x0, c.x1, c.z0, c.z1].every(Number.isFinite)) continue;
          points.push({ x: c.x0 - .8, z: (c.z0 + c.z1) / 2, yaw: Math.PI / 2 },
            { x: c.x1 + .8, z: (c.z0 + c.z1) / 2, yaw: -Math.PI / 2 },
            { x: (c.x0 + c.x1) / 2, z: c.z0 - .8, yaw: 0 },
            { x: (c.x0 + c.x1) / 2, z: c.z1 + .8, yaw: Math.PI });
        }
        const selected = points.find(p => {
          const h = T.ground(zone, p.x, p.z), slope = T.slope(zone, p.x, p.z);
          return Math.abs(p.x) < 115 && Math.abs(p.z) < 115 && Number.isFinite(h) && slope && Math.hypot(slope.e, slope.south) < .5 &&
            !blocked(zone, p.x, p.z, .38) && blocked(zone, p.x + Math.sin(p.yaw) * 1.2, p.z + Math.cos(p.yaw) * 1.2, .38);
        });
        if (!selected) throw Error('No geographic source collider has a stable free approach.');
        Object.assign(camera, selected); T.poseCamera(); paused = false;
        return { selected, collidersExamined: (zone.colliders || []).length, before: window.__SOMA_MOBILITY74__.snapshot() };
      });
      await page.keyboard.down('w');
      let observed;
      try {
        await page.waitForFunction(previous => window.__SOMA_MOBILITY74__.snapshot().stats.collisionStops > previous, setup.before.stats.collisionStops, { timeout: 10000 });
        observed = await page.evaluate(poseSnapshot);
      } finally { await page.keyboard.up('w'); }
      assert(!observed.blocked && Math.hypot(observed.camera.x - setup.selected.x, observed.camera.z - setup.selected.z) < 1.2);
      assert(observed.mobility.stats.collisionStops > setup.before.stats.collisionStops);
      assert(Math.hypot(observed.camera.x - observed.lastOnFoot.x, observed.camera.z - observed.lastOnFoot.z) < .2);
      await shot('source-obstacle-stops-walking'); return { setup, observed };
    });
    await step('existing-ground-vehicle-drive-and-dismount', async () => {
      const setup = await page.evaluate(() => {
        const candidates = zone.vehicles.filter(v => v.pilotable && !v.hidden && !v.ai && !v.disabled && v.condition > 0 &&
          !isFlyingVehicleKind(v.kind) && !isWaterVehicleKind(v.kind) && Math.abs(v.speed || 0) <= .45);
        const v = candidates.find(v => !window.__SOMA_VEHICLES75__.pathBlocked(v, v.x, v.z, v.heading, v.heading) && window.__SOMA_MOBILITY74__.exitPoint(v));
        if (!v) throw Error('No existing stopped pilotable ground vehicle with a verified local exit in this real cell.');
        const before = { id: v.id, x: v.x, z: v.z, heading: v.heading, kind: v.kind, condition: v.condition };
        if (!enterVehicle(v)) throw Error('Existing vehicle owner refused entry.');
        return { before, candidates: candidates.length };
      });
      const before = await page.evaluate(poseSnapshot);
      await page.keyboard.down('w');
      try { await page.waitForFunction(() => (state.statistics.distanceDriven || 0) > 1, null, { timeout: 18000 }); }
      finally { await page.keyboard.up('w'); }
      const driven = await page.evaluate(poseSnapshot);
      assert(driven.driving === setup.before.id && driven.distanceDriven > before.distanceDriven);
      assert(Number.isFinite(driven.ground));
      const exit = await page.evaluate(() => {
        const v = zone.vehicles.find(q => q.id === state.driving), origin = { x: v.x, z: v.z };
        v.speed = 0; const ok = exitVehicle();
        return { ok, origin, camera: { x: camera.x, y: camera.y, z: camera.z }, ground: window.__SOMA_TERRAIN56__.ground(zone, camera.x, camera.z),
          driving: state.driving, blocked: blocked(zone, camera.x, camera.z, .38), lastOnFoot: { ...state.lastOnFoot } };
      });
      assert(exit.ok && !exit.driving && !exit.blocked);
      assert(Math.hypot(exit.camera.x - exit.origin.x, exit.camera.z - exit.origin.z) <= 6.000001);
      assert(Math.abs(exit.camera.y - exit.ground - 1.72) < 1e-6, 'Dismount must pose the camera before the next frame.');
      assert.equal(exit.lastOnFoot.x, exit.camera.x); assert.equal(exit.lastOnFoot.z, exit.camera.z);
      await shot('ground-vehicle-dismount'); return { setup, before, driven, exit, instrumentation: 'Vehicle speed is set to zero only before the bounded dismount check.' };
    });
    await step('native-car-synchronous30-60-120hz-body-contact', async () => {
      const result = await page.evaluate(() => {
        closeModals(); paused = false;
        const V = window.__SOMA_VEHICLES75__, T = window.__SOMA_TERRAIN56__;
        const v = zone.vehicles.find(q => q.pilotable && !q.ai && !q.hidden && !q.disabled && q.condition > 0 && !isFlyingVehicleKind(q.kind) && !isWaterVehicleKind(q.kind));
        if (!v) throw Error('No existing native car for the deterministic frame trial.');
        const authored = { id: v.id, kind: v.kind, x: v.x, z: v.z, heading: v.heading, speed: v.speed, condition: v.condition }, spec = { ...vehicleSpec(v) };
        let lane = null;
        for (const road of zone.roads || []) for (const direction of [1, -1]) {
          if (lane) break;
          const heading = Math.PI / 2 - road.angle + (direction === 1 ? 0 : Math.PI), fx = Math.sin(heading), fz = Math.cos(heading);
          const candidate = { x: road.x - fx * 8, z: road.z - fz * 8, heading };
          if (Math.abs(candidate.x) > 105 || Math.abs(candidate.z) > 105) continue;
          Object.assign(v, candidate, { speed: 0, steering: 0 });
          let clear = true;
          for (let i = 0; i <= 60 && clear; i++) {
            const x = candidate.x + fx * i * .25, z = candidate.z + fz * i * .25;
            clear = !V.pathBlocked(v, x, z, heading, heading); if (clear) Object.assign(v, { x, z });
          }
          if (clear) lane = candidate;
        }
        if (!lane) throw Error('No real source-road lane passes15m swept body and native support checks.');
        const traces = [];
        for (const hz of [30, 60, 120]) {
          Object.assign(v, lane, { speed: 0, steering: 0, condition: authored.condition, lean: 0 });
          const before = V.snapshot(), samples = [];
          for (let i = 0; i < hz * 2; i++) {
            window.__SOMA__.stepVehicle(v.id, { throttle: 1, steer: 0, brake: 0, handbrake: false }, 1 / hz);
            const ground = T.ground(zone, v.x, v.z);
            if (!Number.isFinite(ground) || vehicleBlockedAt(v, v.x, v.z, v.heading) || !Number.isFinite(v.speed)) throw Error('Native vehicle ended a substep without known free support.');
            if (i % hz === 0 || i === hz * 2 - 1) samples.push({ frame: i, x: v.x, z: v.z, speed: v.speed, ground });
          }
          traces.push({ hz, displacementM: Math.hypot(v.x - lane.x, v.z - lane.z), x: v.x, z: v.z, speed: v.speed, before, after: V.snapshot(), samples });
        }
        Object.assign(v, authored); return { authored, spec, lane, traces, current: { id: v.id, kind: v.kind, spec: { ...vehicleSpec(v) } }, terrain: window.__SOMA_TERRAIN75__.snapshot() };
      });
      assert.equal(result.terrain.stepM, 5); assert.equal(result.current.id, result.authored.id); assert.deepEqual(result.current.spec, result.spec);
      for (const trace of result.traces) { assert(trace.displacementM > 1 && trace.displacementM < 15); assert(trace.after.stats.pathChecks > trace.before.stats.pathChecks); assert(trace.after.stats.sweepSamples > trace.before.stats.sweepSamples); }
      const distances = result.traces.map(q => q.displacementM);
      assert(Math.max(...distances) - Math.min(...distances) < .6, 'Frame-rate travel must remain within60cm over the native two-second trial.');
      return result;
    });
    await step('native-car-stops-before-existing-source-building', async () => {
      const result = await page.evaluate(() => {
        const V = window.__SOMA_VEHICLES75__, v = zone.vehicles.find(q => q.pilotable && !q.ai && !q.hidden && !q.disabled && q.condition > 0 && !isFlyingVehicleKind(q.kind) && !isWaterVehicleKind(q.kind));
        if (!v) throw Error('No existing native car for source-contact trial.');
        const original = { x: v.x, z: v.z, heading: v.heading, speed: v.speed, steering: v.steering, condition: v.condition, disabled: v.disabled, lean: v.lean }, spec = vehicleSpec(v);
        let approach = null;
        for (const c of zone.colliders || []) {
          if (approach || c.tag !== 'building' || !c.v53Polygon || ![c.x0, c.x1, c.z0, c.z1].every(Number.isFinite)) continue;
          const candidates = [
            { x: c.x0 - spec.length / 2 - .7, z: (c.z0 + c.z1) / 2, heading: Math.PI / 2 },
            { x: c.x1 + spec.length / 2 + .7, z: (c.z0 + c.z1) / 2, heading: -Math.PI / 2 },
            { x: (c.x0 + c.x1) / 2, z: c.z0 - spec.length / 2 - .7, heading: 0 },
            { x: (c.x0 + c.x1) / 2, z: c.z1 + spec.length / 2 + .7, heading: Math.PI },
          ];
          for (const p of candidates) {
            if (Math.abs(p.x) > 113 || Math.abs(p.z) > 113) continue;
            Object.assign(v, p, { speed: 0, steering: 0 });
            if (V.pathBlocked(v, v.x, v.z, v.heading, v.heading)) continue;
            const before = V.snapshot(), target = { x: p.x + Math.sin(p.heading) * 1.8, z: p.z + Math.cos(p.heading) * 1.8 };
            if (V.pathBlocked(v, target.x, target.z, p.heading, p.heading) && V.snapshot().stats.collisionStops > before.stats.collisionStops) { approach = { pose: p, collider: { tag: c.tag, x0: c.x0, x1: c.x1, z0: c.z0, z1: c.z1 }, target }; break; }
          }
        }
        if (!approach) { Object.assign(v, original); throw Error('No existing source-building body contact has a free native terrain approach.'); }
        Object.assign(v, approach.pose, { speed: 5, steering: 0 }); const before = V.snapshot(), frames = [];
        for (let i = 0; i < 10 && V.snapshot().stats.collisionStops === before.stats.collisionStops; i++) {
          const ok = window.__SOMA__.stepVehicle(v.id, { throttle: 0, steer: 0, brake: 0, handbrake: false }, .1);
          frames.push({ ok, x: v.x, z: v.z, speed: v.speed, blocked: vehicleBlockedAt(v, v.x, v.z, v.heading), ground: window.__SOMA_TERRAIN56__.ground(zone, v.x, v.z) });
        }
        const after = V.snapshot(); Object.assign(v, original); return { id: v.id, kind: v.kind, approach, before, frames, after };
      });
      assert(result.after.stats.collisionStops > result.before.stats.collisionStops); assert(result.frames.length > 0 && result.frames.every(q => !q.blocked && Number.isFinite(q.ground)));
      assert(result.frames.some(q => q.ok === false)); return result;
    });
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.httpErrors, []);
    report.passed = true;
  } catch (error) {
    report.failure = String(error.stack || error); process.exitCode = 1;
    try { if (page) await shot('failure'); } catch (captureError) { report.captureFailure = String(captureError); }
  } finally {
    await browser?.close(); await finishEvidence(report, __filename); report.finishedAt = new Date().toISOString();
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    process.stdout.write(JSON.stringify({ passed: report.passed, report: path.join(output, 'report.json'), steps: report.steps.map(({ name, status }) => ({ name, status })), failure: report.failure }, null, 2) + '\n');
  }
}
main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
