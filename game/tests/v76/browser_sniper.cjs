#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
// Derived from immutable game/tests/v75/browser_sniper.cjs; SHA256 565ca204f6931303ca08490b5b17f589049187da1fc82e51e1d475ce4842767e.
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { sourceEvidence, finishEvidence } = require('./browser_provenance.cjs');
const opts = { url: 'http://127.0.0.1:8787/SOMA_MASSILIA_URBAIN_v0_76.html', chromium: '/usr/bin/chromium', output: '/tmp/massilia-v76-sniper', timeout: 90000 };
for (let i = 2; i < process.argv.length; i++) { const key = process.argv[i].replace(/^--/, ''); assert(Object.hasOwn(opts, key) && process.argv[i + 1]); opts[key] = key === 'timeout' ? Number(process.argv[++i]) : process.argv[++i]; }
const output = path.resolve(opts.output), report = { schema: 'soma/browser-sniper/76/1', startedAt: new Date().toISOString(), passed: false,
  environment: { freshNonPersistentContexts: true, viewport: { width: 1280, height: 720 }, softwareWebGLRequested: true },
  instrumentation: [
    'Each case starts in a fresh browser context and enters the authored red-station through native scene owners. No enemy is created.',
    'The existing sniper retains its authored identity and initial position; native acquisition may move it. Legal clear/wall-blocked player floor poses are selected using the real blocked()/lineBlocked() owners.',
    'Enemy readiness and facing are prepared; other existing enemies are hidden and receive attackClock100 to isolate the sniper from their tactical radio orders. Perception70 and radio72 are reset by their actual reset owner and reacquire through updateAI(.1).',
    'Ticks use complete native updateAI(.1), including cover relocation33 and its preparation guard75. No perception result, radio contact, sight, damage, HUD or save API is replaced.',
    'The heavy76 cases retain an existing authored heavy, original damage14/cooldown1.7 owners and complete updateAI ticks. Smoke prepares one stock in the existing consumable28 owner and maps its first native quickslot before the real F1 key; no sensory API or clock is replaced.',
    'The impact case subtracts one health point from the existing sniper solely to trigger its installed received-hit detection.',
  ], limits: [
    'Prepared encounters and native scene entry are bounded fixtures, not a naturally encountered combat or a human campaign playthrough.',
    'Authored flat-floor combat does not qualify native5m NGF enemy firing, metropolitan traversal or architectural 1:1 fidelity.',
    'SwiftShader screenshots do not certify player GPU performance.',
  ], steps: [], screenshots: [], pageErrors: [], consoleErrors: [], consoleWarnings: [], httpErrors: [], requestFailures: [] };
let browser, context, page, currentStep = 'launch';
async function step(name, run) { currentStep = name; const row = { name, startedAt: new Date().toISOString() }; report.steps.push(row); process.stderr.write('[v76 sniper] ' + name + '\n'); try { row.observation = await run(); row.status = 'passed'; return row.observation; } catch (error) { row.error = String(error.stack || error); row.status = 'failed'; throw error; } finally { row.finishedAt = new Date().toISOString(); } }
async function shot(name) { await page.screenshot({ path: path.join(output, name + '.png') }); report.screenshots.push(name + '.png'); }
async function fresh(role = 'sniper') {
  await context?.close(); context = await browser.newContext({ viewport: report.environment.viewport, locale: 'fr-FR' }); assert.deepEqual((await context.storageState()).origins, []);
  page = await context.newPage(); page.setDefaultTimeout(opts.timeout);
  page.on('pageerror', error => report.pageErrors.push({ step: currentStep, error: String(error.stack || error) }));
  page.on('console', message => { const row = { step: currentStep, text: message.text(), location: message.location() }; if (message.type() === 'error') report.consoleErrors.push(row); if (message.type() === 'warning') report.consoleWarnings.push(row); });
  page.on('response', response => { if (response.status() >= 400) report.httpErrors.push({ step: currentStep, status: response.status(), url: response.url() }); });
  page.on('requestfailed', request => report.requestFailures.push({ step: currentStep, url: request.url(), error: request.failure()?.errorText }));
  assert.equal((await page.goto(opts.url, { waitUntil: 'domcontentloaded' })).status(), 200);
  await page.waitForFunction(() => window.__SOMA_V76__?.ready && window.__SOMA_COMBAT75__ && window.__SOMA_GROUP64__?.ready && window.__SOMA_PERCEPTION70__);
  await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click(); await page.waitForFunction(() => zone?.v52District && !paused);
  return page.evaluate(role => {
    if (!enterZone('v32-red-station')) throw Error('Authored red-station unavailable.'); closeModals(); paused = false; window.__SOMA_V70__.tick(0);
    const C = role === 'sniper' ? window.__SOMA_COMBAT75__ : window.__SOMA_COMBAT76__, P = window.__SOMA_PERCEPTION70__, q = zone.robots.find(q => q.v32Role === role && q.health > 0 && (role === 'rifle' || C.handles(q)));
    if (!q) throw Error('No existing authored ' + role + ' in native red-station roster: ' + JSON.stringify(zone.robots.map(q => ({ id: q.id, role: q.v32Role }))));
    const authored = { id: String(q.id), x: q.x, z: q.z, health: q.health, role: q.v32Role, attackFactor: q.v33AttackFactor ?? 1, damageTakenMult: typeof v27Stats === 'function' ? clamp(v27Stats().damageTakenMult,.35,1.75) : 1 };
    const candidates = [{ x: q.x + 20, z: q.z }, { x: -35, z: 14 }];
    for (const distance of (role === 'heavy' ? [16, 18, 12] : role === 'rifle' ? [8, 10] : [18, 20, 23, 26])) for (let i = 0; i < 32; i++) candidates.push({ x: q.x + Math.sin(i * Math.PI / 16) * distance, z: q.z + Math.cos(i * Math.PI / 16) * distance });
    const legal = p => Math.abs(p.x) < zone.w / 2 - 1 && Math.abs(p.z) < zone.h / 2 - 1 && !blocked(zone, p.x, p.z, .38) && Math.hypot(p.x - q.x, p.z - q.z) >= (role === 'rifle' ? 6 : role === 'heavy' ? 11 : 15) && (role === 'sniper' || Math.hypot(p.x - q.x, p.z - q.z) < (role === 'heavy' ? 19 : 12));
    const clear = candidates.find(p => legal(p) && !lineBlocked(q.x, q.z, p.x, p.z)), wall = candidates.find(p => legal(p) && lineBlocked(q.x, q.z, p.x, p.z));
    if (!clear || (!wall && role !== 'rifle')) throw Error('Authored scene lacks required legal floor poses: ' + JSON.stringify({ role, clear, wall, unit: { id: q.id, x: q.x, z: q.z } }));
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
  }, role);
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
        return { before, saved, imported, after: window.__SOMA_COMBAT75__.snapshot(), restored: { id: restored?.id, attackClock: restored?.attackClock }, coreDomains: Object.keys(campaign.payload.core).filter(k => /^v7[1-6]$/.test(k)), exportedBytes: text.length };
      });
      assert.equal(result.before.combat.activeChannels, 1); assert.equal(result.imported.ok, true); assert.equal(result.after.activeChannels, 0); assert(result.saved.attackClock > 2.4); assert(result.restored.attackClock > 2.3); assert(!Object.keys(result.saved).some(k => /charge|channel|elapsed/i.test(k))); assert.deepEqual(result.coreDomains, []); return { setup, result };
    });
    await step('authored-heavy76-full-charge-retains-original14-damage-owner', async () => {
      const setup = await fresh('heavy'), result = await page.evaluate(() => { const F = window.__qaSniper75; F.start(); const before = F.read(), early = F.tick(6), completed = F.tick(1), after = F.read(); return { before, early, completed, after }; });
      assert.equal(setup.authored.role, 'heavy'); assert.equal(result.before.combat.activeChannels, 1);
      assert.equal(result.early.at(-1).combat.counters.completed, result.before.combat.counters.completed);
      assert.equal(result.after.combat.counters.completed, result.before.combat.counters.completed + 1);
      assert.equal(result.after.damageTaken - result.before.damageTaken, Math.ceil(14 * result.before.attackFactor * result.before.damageTakenMult));
      assert.equal(result.after.combat.activeChannels, 0); return { setup, result };
    });
    await step('heavy76-source-wall-and-received-hit-cancel-with-paid-recovery', async () => {
      const observations = [];
      for (const reason of ['source-wall', 'received-hit']) {
        const setup = await fresh('heavy'), result = await page.evaluate(reason => {
          const F = window.__qaSniper75; F.start(); F.tick(4); const before = F.read();
          if (reason === 'source-wall') F.place(F.wall); else F.q.health -= 1;
          const blockedBySourceWall = lineBlocked(F.q.x, F.q.z, camera.x, camera.z); F.tick(1); const after = F.read();
          F.place(F.clear); F.tick(3); return { before, after, reacquired: F.read(), blockedBySourceWall };
        }, reason);
        assert.equal(result.before.combat.activeChannels, 1); assert.equal(result.after.combat.activeChannels, 0);
        assert.equal(result.after.combat.lastInterruption, reason === 'source-wall' ? 'contact-lost' : 'received-hit');
        if (reason === 'source-wall') assert(result.blockedBySourceWall);
        assert(result.after.clock >= 1.7 / result.after.attackFactor - .11);
        assert.equal(result.after.damageTaken, result.before.damageTaken); assert.equal(result.reacquired.damageTaken, result.before.damageTaken);
        assert.equal(result.reacquired.combat.counters.completed, result.before.combat.counters.completed); observations.push({ reason, setup, result });
      }
      return observations;
    });
    await step('heavy76-shared-four-row-warning-fov-and-real-echo', async () => {
      const setup = await fresh('heavy'), hud = await page.evaluate(() => {
        window.__qaSniper75.start(); const C = window.__SOMA_COMBAT76__, N = window.__SOMA_NETRUNNER72__, before = N.snapshotHUD();
        camera.yaw += Math.PI; N.maintain(); const behind = { channels: C.snapshot().activeChannels, hudHidden: document.getElementById('v72-netrunner-hud').hidden };
        camera.yaw -= Math.PI; N.maintain(); return { before, behind, warningNodes: document.querySelectorAll('#v72-netrunner-hud').length, text: document.getElementById('v72-netrunner-hud').innerText };
      });
      assert.equal(hud.warningNodes, 1); assert(hud.before.telegraphs.some(row => /SALVE LOURDE EN PRÉPARATION/.test(row.title || '')));
      assert(hud.behind.hudHidden && hud.behind.channels === 1); assert.match(hud.text, /Touchez l’unité lourde/);
      await page.keyboard.press('Shift+F2');
      const echo = await page.evaluate(() => { window.__SOMA_TACTICAL73__.scanTargets(); window.__SOMA_TACTICAL73__.maintain(); return window.__SOMA_TACTICAL73__.snapshot(); });
      assert(echo.targets.some(row => /Salve préparée/.test(row.roleLabel) && /Touchez l’unité lourde/.test(row.hint)));
      await shot('03-heavy76-live-echo'); return { setup, hud, echo };
    });
    await step('heavy76-real-cortex-pause-cancels-live-preparation', async () => {
      const setup = await fresh('heavy'), before = await page.evaluate(() => { window.__qaSniper75.start(); return window.__qaSniper75.read(); });
      await page.keyboard.press('Shift+F1'); await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
      const after = await page.evaluate(() => ({ paused, combat: window.__SOMA_COMBAT76__.snapshot(), clock: window.__qaSniper75.q.attackClock }));
      assert(after.paused); assert.equal(before.combat.activeChannels, 1); assert.equal(after.combat.activeChannels, 0); assert(after.clock >= 1.7 / before.attackFactor - .11);
      await shot('04-heavy76-cortex-interruption'); return { setup, before, after };
    });
    await step('heavy76-real-grouped-import-and-raw-reload-retain-owned-recovery', async () => {
      const setup = await fresh('heavy'), result = await page.evaluate(async () => {
        const F = window.__qaSniper75, G = window.__SOMA_GROUP64__; F.start(); F.tick(3); const before = F.read(); window.__SOMA_V32__.snapshotCombat();
        const text = G.exportText(), group = G.validate(text), campaign = JSON.parse(group.payload.campaign), saved = campaign.payload.layers[32].zoneCombat[zone.id].enemies[F.q.id];
        const imported = await G.importText(text, true), restored = zone.robots.find(q => q.id === F.q.id); paused = true; window.__SOMA_V37_SAVE__.flush();
        return { before, saved, imported, after: window.__SOMA_COMBAT76__.snapshot(), restored: { id: restored?.id, attackClock: restored?.attackClock }, coreDomains: Object.keys(campaign.payload.core).filter(k => /^v7[1-6]$/.test(k)), exportedBytes: text.length };
      });
      assert.equal(result.before.combat.activeChannels, 1); assert.equal(result.imported.ok, true); assert.equal(result.after.activeChannels, 0);
      assert(result.saved.attackClock >= 1.7 / result.before.attackFactor - .01); assert(result.restored.attackClock >= result.saved.attackClock - .3);
      assert(!Object.keys(result.saved).some(k => /charge|channel|elapsed/i.test(k))); assert.deepEqual(result.coreDomains, []);
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForFunction(() => window.__SOMA_V76__?.ready && window.__SOMA_V37_SAVE__?.getStatus()?.ready);
      const reloaded = await page.evaluate(id => { paused = true; const q = zone.robots.find(q => q.id === id); return { zone: zone.id, combat: window.__SOMA_COMBAT76__.snapshot(), unit: q ? { id: q.id, health: q.health, clock: q.attackClock } : null }; }, setup.authored.id);
      assert(reloaded.unit); assert.equal(reloaded.combat.activeChannels, 0); assert.equal(reloaded.unit.health, result.saved.health); assert(reloaded.unit.clock >= result.saved.attackClock - .3); return { setup, result, reloaded };
    });
    await step('smoke28-native-F1-consumes-stock-and-revokes-live-personal-sight', async () => {
      const setup = await fresh('rifle'), before = await page.evaluate(() => {
        const F = window.__qaSniper75, S = v28State(); S.consumables.smokeCapsule = 1; S.quickSlots[0] = 'smokeCapsule';
        return { observer: window.__SOMA_PERCEPTION70__.observer(F.q.id), consumablesUsed: S.stats.consumablesUsed, stock: S.consumables.smokeCapsule, now: performance.now(), damageTaken: F.read().damageTaken };
      });
      assert(before.observer.canAttack && before.observer.canTrackCurrent); assert.equal(before.stock, 1);
      await page.keyboard.press('F1');
      const after = await page.evaluate(() => {
        const F = window.__qaSniper75, S = v28State(); F.q.attackClock = 0; const ticks = F.tick(20);
        return { stock: S.consumables.smokeCapsule, consumablesUsed: S.stats.consumablesUsed, now: performance.now(), obscuredUntil: F.q.v28ObscuredUntil, observer: window.__SOMA_PERCEPTION70__.observer(F.q.id), ticks, sourceObscured: window.__SOMA_COMBAT76__.isObscured(F.q), damageTaken: F.read().damageTaken };
      });
      assert.equal(after.stock, 0); assert.equal(after.consumablesUsed, before.consumablesUsed + 1); assert(after.obscuredUntil > after.now && after.obscuredUntil <= after.now + 10000);
      assert.equal(after.sourceObscured, true); assert.equal(after.observer.canTrackCurrent, false); assert.equal(after.observer.canAttack, false);
      assert.equal(after.damageTaken, before.damageTaken); assert(after.ticks.every(row => !row.observer.canAttack));
      return { setup, before, after, limit: 'One smoke stock and the first quickslot are prepared in the existing28 owner. Native F1 consumes it. This proves live sight interruption during the original10s stamp, not acquisition through play or expiry by a wall-clock wait.' };
    });
    assert.deepEqual(report.pageErrors, []); assert.deepEqual(report.consoleErrors, []); assert.deepEqual(report.httpErrors, []); assert.deepEqual(report.requestFailures, []); report.passed = true;
  } catch (error) { report.failure = String(error.stack || error); process.exitCode = 1; try { if (page) await shot('failure-' + currentStep); } catch (captureError) { report.captureFailure = String(captureError); } }
  finally { await browser?.close(); await finishEvidence(report, __filename); report.finishedAt = new Date().toISOString(); await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n'); process.stdout.write(JSON.stringify({ passed: report.passed, report: path.join(output, 'report.json'), steps: report.steps.map(({ name, status }) => ({ name, status })), failure: report.failure }, null, 2) + '\n'); }
}
main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
