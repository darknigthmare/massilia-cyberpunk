#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { sourceEvidence, finishEvidence } = require('./browser_provenance.cjs');
const opts = { url: 'http://127.0.0.1:8777/SOMA_MASSILIA_URBAIN_v0_75.html', chromium: '/usr/bin/chromium', output: '/tmp/massilia-v75-sniper', timeout: 90000 };
for (let i = 2; i < process.argv.length; i++) { const key = process.argv[i].replace(/^--/, ''); assert(Object.hasOwn(opts, key) && process.argv[i + 1]); opts[key] = key === 'timeout' ? Number(process.argv[++i]) : process.argv[++i]; }
const output = path.resolve(opts.output), report = { schema: 'soma/browser-sniper/75/1', startedAt: new Date().toISOString(), passed: false,
  environment: { freshNonPersistentContexts: true, viewport: { width: 1280, height: 720 }, softwareWebGLRequested: true },
  instrumentation: [
    'Each case starts in a fresh browser context and enters the authored red-station through native scene owners. No enemy is created.',
    'The existing sniper retains its authored identity and initial position; native acquisition may move it. Legal clear/wall-blocked player floor poses are selected using the real blocked()/lineBlocked() owners.',
    'Enemy readiness and facing are prepared; other existing enemies are hidden and receive attackClock100 to isolate the sniper from their tactical radio orders. Perception70 and radio72 are reset by their actual reset owner and reacquire through updateAI(.1).',
    'Ticks use complete native updateAI(.1), including cover relocation33 and its preparation guard75. No perception result, radio contact, sight, damage, HUD or save API is replaced.',
    'The impact case subtracts one health point from the existing sniper solely to trigger its installed received-hit detection.',
  ], limits: [
    'Prepared encounters and native scene entry are bounded fixtures, not a naturally encountered combat or a human campaign playthrough.',
    'Authored flat-floor combat does not qualify native5m NGF enemy firing, metropolitan traversal or architectural 1:1 fidelity.',
    'SwiftShader screenshots do not certify player GPU performance.',
  ], steps: [], screenshots: [], pageErrors: [], consoleErrors: [], consoleWarnings: [], httpErrors: [], requestFailures: [] };
let browser, context, page, currentStep = 'launch';
async function step(name, run) { currentStep = name; const row = { name, startedAt: new Date().toISOString() }; report.steps.push(row); process.stderr.write('[v75 sniper] ' + name + '\n'); try { row.observation = await run(); row.status = 'passed'; return row.observation; } catch (error) { row.error = String(error.stack || error); row.status = 'failed'; throw error; } finally { row.finishedAt = new Date().toISOString(); } }
async function shot(name) { await page.screenshot({ path: path.join(output, name + '.png') }); report.screenshots.push(name + '.png'); }
async function fresh() {
  await context?.close(); context = await browser.newContext({ viewport: report.environment.viewport, locale: 'fr-FR' }); assert.deepEqual((await context.storageState()).origins, []);
  page = await context.newPage(); page.setDefaultTimeout(opts.timeout);
  page.on('pageerror', error => report.pageErrors.push({ step: currentStep, error: String(error.stack || error) }));
  page.on('console', message => { const row = { step: currentStep, text: message.text(), location: message.location() }; if (message.type() === 'error') report.consoleErrors.push(row); if (message.type() === 'warning') report.consoleWarnings.push(row); });
  page.on('response', response => { if (response.status() >= 400) report.httpErrors.push({ step: currentStep, status: response.status(), url: response.url() }); });
  page.on('requestfailed', request => report.requestFailures.push({ step: currentStep, url: request.url(), error: request.failure()?.errorText }));
  assert.equal((await page.goto(opts.url, { waitUntil: 'domcontentloaded' })).status(), 200);
  await page.waitForFunction(() => window.__SOMA_V75__?.ready && window.__SOMA_COMBAT75__ && window.__SOMA_GROUP64__?.ready && window.__SOMA_PERCEPTION70__);
  await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click(); await page.waitForFunction(() => zone?.v52District && !paused);
  return page.evaluate(() => {
    if (!enterZone('v32-red-station')) throw Error('Authored red-station unavailable.'); closeModals(); paused = false; window.__SOMA_V70__.tick(0);
    const C = window.__SOMA_COMBAT75__, P = window.__SOMA_PERCEPTION70__, q = zone.robots.find(q => C.handles(q) && q.health > 0);
    if (!q) throw Error('No existing authored sniper in native red-station roster: ' + JSON.stringify(zone.robots.map(q => ({ id: q.id, role: q.v32Role }))));
    const authored = { id: String(q.id), x: q.x, z: q.z, health: q.health, role: q.v32Role, attackFactor: q.v33AttackFactor ?? 1, damageTakenMult: typeof v27Stats === 'function' ? clamp(v27Stats().damageTakenMult,.35,1.75) : 1 };
    const candidates = [{ x: q.x + 20, z: q.z }, { x: -35, z: 14 }];
    for (const distance of [18, 20, 23, 26]) for (let i = 0; i < 32; i++) candidates.push({ x: q.x + Math.sin(i * Math.PI / 16) * distance, z: q.z + Math.cos(i * Math.PI / 16) * distance });
    const legal = p => Math.abs(p.x) < zone.w / 2 - 1 && Math.abs(p.z) < zone.h / 2 - 1 && !blocked(zone, p.x, p.z, .38) && Math.hypot(p.x - q.x, p.z - q.z) >= 15;
    const clear = candidates.find(p => legal(p) && !lineBlocked(q.x, q.z, p.x, p.z)), wall = candidates.find(p => legal(p) && lineBlocked(q.x, q.z, p.x, p.z));
    if (!clear || !wall) throw Error('Authored scene lacks legal clear and source-wall player floor poses.');
    const place = p => Object.assign(camera, { x: p.x, z: p.z, y: 1.72, yaw: Math.atan2(q.x - p.x, q.z - p.z), pitch: 0 }); place(clear);
    for (const other of zone.robots) { other.attackClock = 100; if (other !== q) other.hidden = true; }
    Object.assign(q, { state: 'patrol', detect: 0, heading: Math.atan2(camera.x - q.x, camera.z - q.z), attackClock: 100 });
    P.reset(); C.reset();
    const read = () => ({ health: state.health, armor: state.armor, sniperHealth: q.health, clock: q.attackClock, sniper: { x: q.x, z: q.z, heading: q.heading }, combat: C.snapshot(), observer: P.observer(q.id), damageTaken: window.__SOMA_V32__.getState().combat.damageTaken, attackFactor: q.v33AttackFactor ?? 1, damageTakenMult: typeof v27Stats === 'function' ? clamp(v27Stats().damageTakenMult,.35,1.75) : 1 });
    const tick = count => { const rows = []; for (let i = 0; i < count; i++) { updateAI(.1); rows.push(read()); } return rows; };
    const acquisition = [];
    for (let i = 0; i < 40 && !P.observer(q.id)?.canAttack; i++) acquisition.push(...tick(1));
    const contact = P.observer(q.id);
    if (!contact?.canAttack || !contact.canTrackCurrent || contact.lastSense !== 'visual') throw Error('Real personal acquisition failed: ' + JSON.stringify(acquisition));
    const start = () => { q.attackClock = 0; const rows = []; for (let i = 0; i < 5 && C.snapshot().activeChannels === 0; i++) rows.push(...tick(1)); if (C.snapshot().activeChannels !== 1) throw Error('The real sniper never began preparation: ' + JSON.stringify(rows)); return rows; };
    window.__qaSniper75 = { q, clear, wall, place, tick, read, start };
    return { authored, clear, wall, acquisition, contact, prepared: read(), sightNGFActive: window.__SOMA_SIGHT61__.activeFor(zone) };
  });
}
async function main() {
  await fs.mkdir(output, { recursive: true }); report.provenance = await sourceEvidence(__filename);
  try {
    browser = await chromium.launch({ executablePath: opts.chromium, headless: true, args: ['--no-sandbox', '--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] }); report.environment.chromium = browser.version(); report.environment.playwright = require('playwright/package.json').version;
    await step('authored-sniper-full-charge-and-original-damage-owner', async () => {
      const setup = await fresh(); const result = await page.evaluate(() => {
        const F = window.__qaSniper75; F.start(); const before = F.read(), early = F.tick(10), completed = F.tick(1), after = F.read(); return { before, early, completed, after };
      });
      report.diagnosticFullCharge = { setup, result };
      assert.equal(result.before.combat.activeChannels, 1); assert.equal(result.early.at(-1).combat.counters.completed, result.before.combat.counters.completed);
      assert.equal(result.after.combat.counters.completed, result.before.combat.counters.completed + 1);
      assert.equal(result.after.damageTaken - result.before.damageTaken, Math.ceil(23 * result.before.attackFactor * result.before.damageTakenMult)); assert.equal(result.after.combat.activeChannels, 0); return { setup, result };
    });
    await step('source-wall-cancels-charge-and-prevents-stale-reacquisition-shot', async () => {
      const setup = await fresh(); const result = await page.evaluate(() => {
        const F = window.__qaSniper75; F.start(); F.tick(8); const charged = F.read(); F.place(F.wall); const wallBlocked = lineBlocked(F.q.x, F.q.z, camera.x, camera.z); F.tick(1); const interrupted = F.read();
        F.place(F.clear); F.tick(8); const reacquired = F.read(); return { charged, wallBlocked, interrupted, reacquired };
      });
      assert(result.charged.combat.channels[0].progress > .7); assert(result.wallBlocked); assert.equal(result.interrupted.combat.activeChannels, 0); assert.equal(result.interrupted.combat.lastInterruption, 'contact-lost'); assert(result.interrupted.clock > 2.4);
      assert.equal(result.reacquired.combat.counters.completed, result.charged.combat.counters.completed); assert.equal(result.reacquired.damageTaken, result.charged.damageTaken); return { setup, result };
    });
    await step('received-impact-cancels-with-paid-recovery', async () => {
      const setup = await fresh(); const result = await page.evaluate(() => { const F = window.__qaSniper75; F.start(); F.tick(4); const before = F.read(); F.q.health -= 1; F.tick(1); return { before, after: F.read() }; });
      assert.equal(result.after.combat.activeChannels, 0); assert.equal(result.after.combat.lastInterruption, 'received-hit'); assert(result.after.clock > 2.4); assert.equal(result.after.damageTaken, result.before.damageTaken); return { setup, result };
    });
    await step('shared-warning-real-fov-and-echo', async () => {
      const setup = await fresh();
      const hud = await page.evaluate(() => { window.__qaSniper75.start(); const C = window.__SOMA_COMBAT75__, N = window.__SOMA_NETRUNNER72__, before = N.snapshotHUD(); camera.yaw += Math.PI; N.maintain(); const behind = { channels: C.snapshot().activeChannels, hudHidden: document.getElementById('v72-netrunner-hud').hidden }; camera.yaw -= Math.PI; N.maintain(); return { before, behind, warningNodes: document.querySelectorAll('#v72-netrunner-hud').length, text: document.getElementById('v72-netrunner-hud').innerText }; });
      assert.equal(hud.warningNodes, 1); assert(hud.before.telegraphs.some(row => /TIR DE PRÉCISION/.test(row.title || ''))); assert(hud.behind.hudHidden && hud.behind.channels === 1); assert.match(hud.text, /Touchez le tireur/);
      await page.keyboard.press('Shift+F2');
      const echo = await page.evaluate(() => { window.__SOMA_TACTICAL73__.scanTargets(); window.__SOMA_TACTICAL73__.maintain(); return window.__SOMA_TACTICAL73__.snapshot(); });
      report.diagnosticEcho = { setup, hud, echo };
      assert(echo.targets.some(row => /Tir préparé/.test(row.roleLabel) && /Touchez le tireur/.test(row.hint))); await shot('01-sniper-live-echo'); return { setup, hud, echo };
    });
    await step('real-cortex-pause-cancels-live-channel', async () => {
      const setup = await fresh(); const before = await page.evaluate(() => { window.__qaSniper75.start(); return window.__qaSniper75.read(); });
      await page.keyboard.press('Shift+F1'); await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
      const pausedState = await page.evaluate(() => ({ paused, combat: window.__SOMA_COMBAT75__.snapshot(), clock: window.__qaSniper75.q.attackClock })); assert(pausedState.paused); assert.equal(pausedState.combat.activeChannels, 0); assert(pausedState.clock > 2.4); await shot('02-sniper-cortex-interruption'); return { setup, before, pausedState };
    });
    await step('live-real-grouped-import-clears-channel-preserves-owned-recovery', async () => {
      const setup = await fresh(); const result = await page.evaluate(async () => {
        const F = window.__qaSniper75, G = window.__SOMA_GROUP64__; F.start(); F.tick(4); const before = F.read(); window.__SOMA_V32__.snapshotCombat(); const text = G.exportText(), group = G.validate(text), campaign = JSON.parse(group.payload.campaign);
        const saved = campaign.payload.layers[32].zoneCombat[zone.id].enemies[F.q.id], imported = await G.importText(text, true), restored = zone.robots.find(q => q.id === F.q.id);
        return { before, saved, imported, after: window.__SOMA_COMBAT75__.snapshot(), restored: { id: restored?.id, attackClock: restored?.attackClock }, coreDomains: Object.keys(campaign.payload.core).filter(k => /^v7[1-5]$/.test(k)), exportedBytes: text.length };
      });
      assert.equal(result.before.combat.activeChannels, 1); assert.equal(result.imported.ok, true); assert.equal(result.after.activeChannels, 0); assert(result.saved.attackClock > 2.4); assert(result.restored.attackClock > 2.3); assert(!Object.keys(result.saved).some(k => /charge|channel|elapsed/i.test(k))); assert.deepEqual(result.coreDomains, []); return { setup, result };
    });
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.httpErrors, []); assert.deepEqual(report.requestFailures, []); report.passed = true;
  } catch (error) { report.failure = String(error.stack || error); process.exitCode = 1; try { if (page) await shot('failure-' + currentStep); } catch (captureError) { report.captureFailure = String(captureError); } }
  finally { await browser?.close(); await finishEvidence(report, __filename); report.finishedAt = new Date().toISOString(); await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n'); process.stdout.write(JSON.stringify({ passed: report.passed, report: path.join(output, 'report.json'), steps: report.steps.map(({ name, status }) => ({ name, status })), failure: report.failure }, null, 2) + '\n'); }
}
main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
