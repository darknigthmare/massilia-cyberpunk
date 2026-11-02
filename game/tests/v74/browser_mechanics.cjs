#!/usr/bin/env node
'use strict';

// Bounded integration of the installed v20/v42/v56 movement and v32 combat
// owners. Native actors/vehicles are retained; setup mutations are reported.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { sourceEvidence } = require('./browser_provenance.cjs');
const opts = { url: 'http://127.0.0.1:8774/SOMA_MASSILIA_URBAIN_v0_74.html', chromium: '/usr/bin/chromium', output: '/tmp/massilia-v74-mechanics', timeout: 90000 };
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const key = argv[i].replace(/^--/, '');
  assert(Object.hasOwn(opts, key) && argv[i + 1], 'Unknown or incomplete argument: ' + argv[i]);
  opts[key] = key === 'timeout' ? Number(argv[++i]) : argv[++i];
}
const output = path.resolve(opts.output);
const report = { schema: 'soma/browser-mechanics/74/1', passed: false, startedAt: new Date().toISOString(),
  environment: { freshNonPersistentContext: true, softwareWebGLRequested: true, viewport: { width: 1280, height: 720 } },
  instrumentation: [
    'A collision/terrain-checked initial pose is selected in the actual geographic scene; subsequent walking uses the installed controller and keyboard input.',
    'The existing enterVehicle/exitVehicle owners are called on an existing pilotable vehicle. No road, terrain, collider or vehicle is created.',
    'A native authored red zone is entered. Existing medic/ally health, initial poses, readiness and combat state are prepared explicitly; the player occupies a real unobstructed floor pose visible to the medic.',
    'Combat ticks call the real updateAI(.1), which reaches the installed v32 effect owner. No combat, perception, raycast or save API is replaced.',
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
  process.stderr.write('[v74 mechanics] ' + name + '\n');
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
      await page.waitForFunction(() => window.__SOMA_V74__?.ready && window.__SOMA_MOBILITY74__?.ready && window.__SOMA_COMBAT_SUPPORT74__);
      await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click();
      await page.waitForFunction(() => zone?.v52District && !paused && window.__SOMA_TERRAIN56__.activeFor(zone));
      return page.evaluate(() => ({ edition: window.__SOMA_V74__.snapshot(), geographicZone: zone.id,
        buildings: zone.v68Architecture.buildings, mobility: window.__SOMA_MOBILITY74__.snapshot(), support: window.__SOMA_COMBAT_SUPPORT74__.snapshot() }));
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
        const v = candidates.find(v => window.__SOMA_MOBILITY74__.exitPoint(v));
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
    await step('native-medical-channel-heal-and-counterplay', async () => {
      const result = await page.evaluate(() => {
        if (!enterZone('v32-red-station')) throw Error('Native red zone unavailable.');
        closeModals(); paused = false; window.__SOMA_V70__.tick(0);
        const S = window.__SOMA_COMBAT_SUPPORT74__, medic = zone.robots.find(q => S.handles(q) && q.health > 0);
        if (!medic) throw Error('No native medic in red station.');
        const ally = zone.robots.find(q => q !== medic && q.v32Enemy && q.health > 0 && q.v33Faction === medic.v33Faction);
        if (!ally) throw Error('No native ally of the same faction.');
        const original = { zone: zone.id, medic: { ...medic }, ally: { ...ally } };
        let clear = null, wall = null; const clearPoses = [];
        for (let r = 3; r <= 15; r += 2) for (let a = 0; a < 32; a++) {
          const p = safePosition(zone, { x: medic.x + Math.sin(a * Math.PI / 16) * r, z: medic.z + Math.cos(a * Math.PI / 16) * r, yaw: 0 });
          const d = Math.hypot(p.x - medic.x, p.z - medic.z);
          if (d < 2 || d >= 16 || blocked(zone, p.x, p.z, .38)) continue;
          if (lineBlocked(medic.x, medic.z, p.x, p.z)) wall ||= p; else { clear ||= p; clearPoses.push(p); }
        }
        if (!clear || !wall) throw Error('Native red zone lacks both clear and wall-blocked ally poses.');
        let cameraPose = null;
        for (const allyPose of clearPoses) {
          const ax = allyPose.x - medic.x, az = allyPose.z - medic.z, ad = Math.hypot(ax, az);
          const opposite = clearPoses.find(p => {
            const px = p.x - medic.x, pz = p.z - medic.z, pd = Math.hypot(px, pz);
            return pd >= 5 && pd <= 12 && (ax * px + az * pz) / (ad * pd) < -.6;
          });
          if (opposite) { clear = allyPose; cameraPose = opposite; break; }
        }
        if (!cameraPose) throw Error('No two real clear floor poses place ally opposite the player around the native medic.');
        Object.assign(camera, { x: cameraPose.x, z: cameraPose.z, y: 1.72, yaw: Math.atan2(medic.x - cameraPose.x, medic.z - cameraPose.z), pitch: 0 });
        const facingPlayer = () => Math.atan2(camera.x - medic.x, camera.z - medic.z);
        for (const q of zone.robots) { if (q.v32Enemy && q.health > 0) q.health = q.maxHealth; if (q !== medic && S.handles(q)) q.attackClock = 100; }
        Object.assign(ally, { x: clear.x, z: clear.z });
        Object.assign(medic, { state: 'combat', detect: 1.2, searchClock: 5, attackClock: 100, heading: facingPlayer() });
        window.__SOMA_PERCEPTION70__.reset(); S.reset();
        const ticks = count => { const rows = []; for (let i = 0; i < count; i++) { updateAI(.1); rows.push({ health: ally.health, medicState: medic.state, medicClock: medic.attackClock,
          playerHealth: state.health, recoveryGrace: state.recoveryGrace, perception: window.__SOMA_PERCEPTION70__.observer(medic.id), support: S.snapshot() }); } return rows; };
        const contactTicks = ticks(1), personalContact = window.__SOMA_PERCEPTION70__.observer(medic.id);
        if (!personalContact?.canAttack || !personalContact.canTrackCurrent || personalContact.lastSense !== 'visual')
          throw Error('The real perception owner did not confirm the medic player contact: ' + JSON.stringify(contactTicks));
        ally.health = Math.max(1, ally.maxHealth - 40); medic.attackClock = 0;
        const beforeHealth = ally.health, healing = ticks(14);
        if (ally.health !== beforeHealth + 18) throw Error('Real v32 branch did not apply exactly +18: ' + JSON.stringify(healing));
        if (!healing.some(row => row.perception?.canAttack === false && row.support.activeChannels === 1))
          throw Error('The opposite-ally fixture never exercised healing after losing direct player attack permission.');
        const completed = S.snapshot();
        const acquireAndStart = () => {
          Object.assign(ally, { x: clear.x, z: clear.z, health: Math.max(1, ally.maxHealth - 40) });
          Object.assign(medic, { state: 'combat', detect: 1.2, searchClock: 5, attackClock: 100, heading: facingPlayer() });
          window.__SOMA_PERCEPTION70__.reset(); S.reset(); ticks(1);
          const contact = window.__SOMA_PERCEPTION70__.observer(medic.id);
          if (!contact?.canAttack || !contact.canTrackCurrent || contact.lastSense !== 'visual')
            throw Error('A new interruption trial lacks real personal visual contact: ' + JSON.stringify(contact));
          medic.attackClock = 0; ticks(1); return contact;
        };
        const hitContact = acquireAndStart(); const beforeHit = { health: ally.health, contact: hitContact, support: S.snapshot() };
        if (!S.isPreparing(medic)) throw Error('No real channel before controlled medic impact.');
        medic.health -= 1; const impact = ticks(1); const afterHit = { health: ally.health, clock: medic.attackClock, support: S.snapshot() };
        if (S.isPreparing(medic) || ally.health !== beforeHit.health || medic.attackClock < 3) throw Error('Impact failed to interrupt without refund.');
        const wallContact = acquireAndStart(); const beforeWall = { health: ally.health, contact: wallContact, support: S.snapshot() };
        if (!S.isPreparing(medic)) throw Error('No real channel before source-wall occlusion.');
        Object.assign(ally, { x: wall.x, z: wall.z }); const occluded = lineBlocked(medic.x, medic.z, ally.x, ally.z); ticks(1);
        const afterWall = { health: ally.health, clock: medic.attackClock, support: S.snapshot() };
        if (!occluded || S.isPreparing(medic) || ally.health !== beforeWall.health || medic.attackClock < 3) throw Error('Native wall failed to interrupt.');
        const menuContact = acquireAndStart();
        const liveBeforeMenu = S.snapshot(); if (!S.isPreparing(medic)) throw Error('No real channel before menu.');
        window.__qaStartMedicalTrial74 = acquireAndStart;
        window.__qaMedicalActors74 = { medic, ally };
        return { original, clear, wall, cameraPose, contactTicks, personalContact,
          playerLineClear: !lineBlocked(medic.x, medic.z, camera.x, camera.z), beforeHealth, healing, completed, beforeHit, impact, afterHit, beforeWall, afterWall, menuContact, liveBeforeMenu };
      });
      assert.equal(result.completed.counters.completed, 1);
      await page.keyboard.press('Shift+F2');
      await page.waitForFunction(id => window.__SOMA_TACTICAL73__.snapshot().targets.some(q => q.id === id && /Reprise médicale/.test(q.roleLabel)), result.original.medic.id);
      await page.waitForFunction(() => Array.from(document.querySelectorAll('.v73-tactical-marker')).some(node => {
        const rect = node.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && /Reprise médicale/.test(node.textContent) && /Touchez le médecin/.test(node.textContent);
      }), null, { timeout: 5000 });
      result.liveEcho = await page.evaluate(id => ({ support: window.__SOMA_COMBAT_SUPPORT74__.snapshot(),
        target: window.__SOMA_TACTICAL73__.snapshot().targets.find(q => q.id === id),
        markerTexts: Array.from(document.querySelectorAll('.v73-tactical-marker')).map(node => node.innerText) }), result.original.medic.id);
      assert.equal(result.liveEcho.support.activeChannels, 1);
      assert.match(result.liveEcho.target.hint, /Touchez le médecin/);
      assert(result.liveEcho.markerTexts.some(text => /Reprise médicale/.test(text) && /Touchez le médecin/.test(text)));
      await shot('medic-live-echo-counterplay');
      await page.keyboard.press('Shift+F1'); await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
      const menu = await page.evaluate(() => ({ paused, support: window.__SOMA_COMBAT_SUPPORT74__.snapshot() }));
      assert(menu.paused && menu.support.activeChannels === 0);
      await shot('medic-interrupted-by-cortex'); await page.locator('#v70-tactics [data-v70-close]').click();
      await page.waitForFunction(() => !paused);
      return { ...result, realMenu: menu };
    });
    await step('native-live-medical-channel-cleared-by-real-import', async () => {
      const previous = report.steps.find(row => row.name === 'native-medical-channel-heal-and-counterplay').observation;
      // A fresh native scene isolates this trial from the preceding live Cortex
      // pause, elapsed perception memory and v33 tactical support orders.
      await context.close();
      context = await browser.newContext({ viewport: report.environment.viewport, locale: 'fr-FR' });
      assert.deepEqual((await context.storageState()).origins, []);
      report.environment.contextsCreated = 2;
      page = await context.newPage(); page.setDefaultTimeout(opts.timeout);
      page.on('pageerror', error => report.pageErrors.push({ step: currentStep, error: String(error.stack || error) }));
      page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push({ step: currentStep, text: message.text(), location: message.location() }); });
      page.on('response', response => { if (response.status() >= 400) report.httpErrors.push({ step: currentStep, status: response.status(), url: response.url() }); });
      assert.equal((await page.goto(opts.url, { waitUntil: 'domcontentloaded' })).status(), 200);
      await page.waitForFunction(() => window.__SOMA_V74__?.ready && window.__SOMA_GROUP64__?.ready && window.__SOMA_COMBAT_SUPPORT74__);
      await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click();
      await page.waitForFunction(() => zone?.v52District && !paused);
      const result = await page.evaluate(async ({ clear, cameraPose }) => {
        if (!enterZone('v32-red-station')) throw Error('Native red zone unavailable for isolated import.');
        closeModals(); paused = false; window.__SOMA_V70__.tick(0);
        const S = window.__SOMA_COMBAT_SUPPORT74__, medic = zone.robots.find(q => S.handles(q) && q.health > 0);
        const ally = zone.robots.find(q => q !== medic && q.v32Enemy && q.health > 0 && q.v33Faction === medic.v33Faction);
        if (!medic || !ally || blocked(zone, clear.x, clear.z, .38) || blocked(zone, cameraPose.x, cameraPose.z, .38) ||
          lineBlocked(medic.x, medic.z, cameraPose.x, cameraPose.z) || lineBlocked(medic.x, medic.z, clear.x, clear.z))
          throw Error('The isolated native scene does not support the verified source floor poses.');
        Object.assign(camera, { x: cameraPose.x, z: cameraPose.z, y: 1.72, yaw: Math.atan2(medic.x - cameraPose.x, medic.z - cameraPose.z), pitch: 0 });
        for (const q of zone.robots) { if (q.v32Enemy && q.health > 0) q.health = q.maxHealth; if (q !== medic && S.handles(q)) q.attackClock = 100; }
        Object.assign(ally, { x: clear.x, z: clear.z });
        Object.assign(medic, { state: 'combat', detect: 1.2, searchClock: 5, attackClock: 100, heading: Math.atan2(camera.x - medic.x, camera.z - medic.z) });
        window.__SOMA_PERCEPTION70__.reset(); S.reset(); updateAI(.1);
        const contact = window.__SOMA_PERCEPTION70__.observer(medic.id);
        if (!contact?.canAttack || !contact.canTrackCurrent || contact.lastSense !== 'visual') throw Error('Isolated import lacks real personal visual contact.');
        ally.health = Math.max(1, ally.maxHealth - 40); medic.attackClock = 0; updateAI(.1);
        const before = S.snapshot();
        if (before.activeChannels !== 1) throw Error('Native channel was not active before grouped import: ' + JSON.stringify({ before, contact, medic, ally, paused, playerHealth: state.health }));
        window.__SOMA_V32__.snapshotCombat();
        const G = window.__SOMA_GROUP64__, text = G.exportText(), checked = G.validate(text), campaign = JSON.parse(checked.payload.campaign);
        const savedMedic = campaign.payload.layers[32].zoneCombat[zone.id].enemies[medic.id];
        const imported = await G.importText(text, true), after = S.snapshot();
        const restoredMedic = zone.robots.find(q => q.id === medic.id);
        return { freshIsolatedContext: true, before, contact, imported, after, savedMedic, restoredMedic: { id: restoredMedic?.id, attackClock: restoredMedic?.attackClock }, groupedModules: checked.summary.modules,
          newCampaignDomains: Object.keys(campaign.payload.core).filter(key => /^v7[1-9]$/.test(key)),
          exportedBytes: new TextEncoder().encode(text).byteLength };
      }, { clear: previous.clear, cameraPose: previous.cameraPose });
      assert.equal(result.imported.ok, true); assert.equal(result.before.activeChannels, 1); assert.equal(result.after.activeChannels, 0);
      assert.equal(result.savedMedic.attackClock, 3.2); assert(result.restoredMedic.attackClock >= 3.1);
      assert(!Object.keys(result.savedMedic).some(key => /channel|elapsed|support74/i.test(key)));
      assert.deepEqual(result.newCampaignDomains, []); return result;
    });
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.httpErrors, []);
    report.passed = true;
  } catch (error) {
    report.failure = String(error.stack || error); process.exitCode = 1;
    try { if (page) await shot('failure'); } catch (captureError) { report.captureFailure = String(captureError); }
  } finally {
    await browser?.close();
    report.provenanceFinished = await sourceEvidence(__filename);
    report.sourceSetUnchanged = report.provenance.aggregateSHA256 === report.provenanceFinished.aggregateSHA256;
    report.finishedAt = new Date().toISOString();
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    process.stdout.write(JSON.stringify({ passed: report.passed, report: path.join(output, 'report.json'), steps: report.steps.map(({ name, status }) => ({ name, status })), failure: report.failure }, null, 2) + '\n');
  }
}
main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
