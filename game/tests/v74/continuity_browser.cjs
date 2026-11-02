#!/usr/bin/env node
'use strict';

// Derived from immutable game/tests/v73/continuity_browser.cjs.
// Parent SHA256: 3d54d9ff2399971b63be70c2c247840e303f7bc8752a1d1cea30e9c43291dfbf; v74 executes its own built pages.
const { sourceEvidence } = require('./browser_provenance.cjs');

/** Real v70/v71/v73 grouped exports imported into v74 in isolated browser contexts.
 * This is a bounded integration scenario, not a player campaign or combat test.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');

function options(argv) {
  const result = { url: 'http://127.0.0.1:8774/SOMA_MASSILIA_URBAIN_v0_74.html', chromium: null, output: null, timeout: 90000 };
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (flag === '--help' || flag === '-h') {
      process.stdout.write('Usage: node game/tests/v74/continuity_browser.cjs [--url URL] [--chromium PATH] [--output DIRECTORY] [--timeout MILLISECONDS]\n');
      return null;
    }
    if (!['--url', '--chromium', '--output', '--timeout'].includes(flag)) throw Error('Unknown option: ' + flag);
    const value = argv[++i];
    if (!value || value.startsWith('--')) throw Error('Missing value for ' + flag);
    result[flag.slice(2)] = flag === '--timeout' ? Number(value) : value;
  }
  assert(['http:', 'https:'].includes(new URL(result.url).protocol));
  assert(/\/SOMA_MASSILIA_URBAIN_v0_74\.html$/.test(new URL(result.url).pathname), '--url must select the current v74 campaign.');
  assert(Number.isInteger(result.timeout) && result.timeout >= 5000 && result.timeout <= 300000);
  return result;
}
const errorRecord = error => ({ name: error?.name || 'Error', message: String(error?.message || error), stack: String(error?.stack || '').slice(0, 10000) });
const sha256 = text => crypto.createHash('sha256').update(text).digest('hex');

// Executed in the actual page. Authoritative domains are read, never replaced.
function snapshot() {
  const copy = value => JSON.parse(JSON.stringify(value));
  const saver = window.__SOMA_V37_SAVE__, envelope = saver.snapshot();
  saver.validate(envelope);
  const core = envelope.payload.core;
  const progressionKeys = ['health', 'armor', 'debt', 'memory', 'tension', 'contracts', 'campaign25', 'campaign26',
    'player27', 'player28', 'player29', 'v35Body', 'v35Infrastructure', 'v35Stories', 'v35Characters',
    'v36Commerce', 'v36Bosses', 'v37Stories', 'v37Justice'];
  return {
    saveKey: saver.key, saveStatus: saver.getStatus(), credits: state.credits, zone: state.zone,
    progression: copy(Object.fromEntries(progressionKeys.filter(key => Object.hasOwn(core, key)).map(key => [key, core[key]]))),
    v67: copy(core.v67), v70: copy(state.v70), savedV70: copy(core.v70),
    augmentation: window.__SOMA_V70__.snapshot(), deck: copy(window.__SOMA_V42__.state().cyberdeck),
    module42Key: window.__SOMA_V42__.key,
    futureDomains: Object.keys(core).filter(key => /^(?:v|player|campaign)(\d+)/.test(key) && Number(key.match(/\d+/)[0]) > 70),
    radio: window.__SOMA_CONTACT_SHARING72__?.snapshot() || null,
    netrunner: window.__SOMA_NETRUNNER72__?.snapshot() || null,
    tactics: window.__SOMA_TACTICAL73__?.snapshot() || null,
  };
}

function assertRestored(actual, expected, label) {
  assert(actual.saveStatus.ready && !actual.saveStatus.blocked, label + ': save owner is unavailable.');
  assert.equal(actual.saveKey, 'soma-massilia.continuity.v37');
  assert.equal(actual.credits, expected.credits, label + ': credits changed.');
  assert.equal(actual.zone, expected.zone, label + ': location changed.');
  assert.deepEqual(actual.progression, expected.progression, label + ': campaign/player progress changed.');
  assert.equal(actual.v67.schema, 'soma-v67/1');
  assert.deepEqual(actual.v67.conversations, expected.v67.conversations, label + ': real conversation progress changed.');
  assert.deepEqual(actual.v67.ambientSeen, expected.v67.ambientSeen, label + ': ambient progress changed.');
  for (const [district, count] of Object.entries(expected.v67.districtVisits)) {
    assert(actual.v67.districtVisits[district] >= count, label + ': district progress was lost.');
  }
  assert.deepEqual(actual.v70, expected.v70, label + ': cooldowns/trace/statistics changed.');
  assert.deepEqual(actual.savedV70, expected.v70, label + ': real campaign serializer differs.');
  assert.deepEqual(actual.augmentation.persisted, expected.v70, label + ': augmentation owner differs.');
  assert.deepEqual(actual.deck, expected.deck, label + ': shared v42 cyberdeck changed.');
  assert.equal(actual.module42Key, expected.module42Key);
  assert.equal(actual.module42Key, 'soma-massilia.recovery.v42');
  assert.equal(actual.augmentation.energy, actual.deck.energy, label + ': Cortex energy differs from its v42 owner.');
  assert(Object.values(actual.augmentation.active).every(value => value === 0), label + ': active implant survived restoration.');
  assert.equal(actual.augmentation.barrierRemaining, 0, label + ': temporary protection survived restoration.');
  assert.deepEqual(actual.futureDomains, [], label + ': a new campaign domain appeared.');
  assert.equal(actual.radio?.contactCount, 0, label + ': transient radio contact remains.');
  assert.equal(actual.netrunner?.activeChannels, 0, label + ': transient netrunner channel remains.');
  assert.equal(actual.tactics?.scanActive, false, label + ': v73 tactical scan survived restoration.');
  assert.equal(actual.tactics?.visibleTargets, 0, label + ': v73 tactical targets survived restoration.');
}

async function main() {
  const args = options(process.argv.slice(2));
  if (!args) return;
  const output = args.output ? path.resolve(args.output) : await fs.mkdtemp(path.join(os.tmpdir(), 'massilia-v74-continuity-'));
  await fs.mkdir(output, { recursive: true });
  const report = {
    schema: 'soma/browser-continuity/74/1', provenance: await sourceEvidence(__filename), startedAt: new Date().toISOString(), url: args.url, output, passed: false,
    environment: { headless: true, freshNonPersistentContexts: true, viewport: { width: 1440, height: 1000 }, softwareWebGLRequested: true },
    interventions: [
      'Every historical export is downloaded from its actual v70/v71/v73 page with the real grouped-export button; no historical save is fabricated.',
      'npcDialogue is called once on an existing generic civilian in the loaded scene to obtain nonempty v67 progress; no actor is created or moved.',
      'paused=true freezes comparison after real Cortex activation; simulation is not replaced.',
      'Target credits are increased by 17 only to prove replacement by the exported historical value.',
      'Invalid derivatives of the actual export use the public grouped core to repair checksums, so schema/ownership validation is exercised beyond corruption detection.',
      'Rejection comparisons normalize only core.updatedAt synthesized by snapshotSave on every read. A no-operation control records that field; stored save bytes, including their persisted timestamps, remain strictly compared.',
    ],
    limits: [
      'Fresh integration scenarios do not represent a real player save or a completed campaign; populated progress covers an existing civilian conversation, district visits and Cortex use.',
      'No combat enemies, radio contacts or netrunner channels are injected. Empty transient radio/netrunner state after restoration does not prove reset during live combat.',
      'District visits may increase when the real importer/reload enters the saved zone; conversations and other compared progress must remain exact.',
      'Headless SwiftShader does not qualify a player GPU, game performance, complete traversal or architectural fidelity.',
    ],
    steps: [], screenshots: [], pageErrors: [], consoleErrors: [], consoleWarnings: [], httpErrors: [], requestFailures: [],
  };
  let browser, context, page, currentStep = 'launch', currentEdition = null, failure;
  const record = (list, value) => { if (list.length < 100) list.push({ step: currentStep, edition: currentEdition, ...value }); else report.eventOverflow = true; };
  async function step(name, run) {
    currentStep = name;
    const item = { name, startedAt: new Date().toISOString(), status: 'running' };
    report.steps.push(item);
    process.stderr.write('[v74 continuity] ' + name + '\n');
    try { item.observation = await run(); item.status = 'passed'; return item.observation; }
    catch (error) { item.error = errorRecord(error); item.status = 'failed'; throw error; }
    finally { item.finishedAt = new Date().toISOString(); }
  }
  async function screenshot(name) {
    const filename = name + '.png';
    await page.screenshot({ path: path.join(output, filename), timeout: args.timeout });
    report.screenshots.push(filename);
  }
  async function ready(edition) {
    await page.waitForFunction(v => window.__SOMA_V70__?.ready === true && window.__SOMA_GROUP64__?.ready === true &&
      window.__SOMA_V37_SAVE__?.getStatus()?.ready === true && window.__SOMA_TERRAIN56__?.grid &&
      (v === 70 || window['__SOMA_V' + v + '__']) &&
      (v !== 73 || window.__SOMA_V73__?.ready === true) && (v !== 74 || window.__SOMA_V74__?.ready === true) && document.title.includes('0.' + v), edition, { timeout: args.timeout });
    // Historical runtime setup can overwrite the static HTML title. Its own ready
    // API and final title are both required; no production edition API is patched.
    assert.match(await page.title(), new RegExp('SOMA//MASSILIA 0\\.' + edition + '(?: | —)'));
  }
  async function openEdition(edition) {
    currentEdition = edition;
    context = await browser.newContext({ viewport: report.environment.viewport, locale: 'fr-FR', acceptDownloads: true });
    assert.deepEqual((await context.storageState()).origins, [], 'A new context must have no inherited storage.');
    page = await context.newPage();
    page.setDefaultTimeout(args.timeout);
    page.setDefaultNavigationTimeout(args.timeout);
    page.on('pageerror', error => record(report.pageErrors, errorRecord(error)));
    page.on('console', message => {
      const entry = { text: message.text().slice(0, 6000), location: message.location() };
      if (message.type() === 'error') record(report.consoleErrors, entry);
      if (message.type() === 'warning') record(report.consoleWarnings, entry);
    });
    page.on('response', response => { if (response.status() >= 400) record(report.httpErrors, { status: response.status(), url: response.url() }); });
    page.on('requestfailed', request => record(report.requestFailures, { url: request.url(), error: request.failure()?.errorText }));
    const url = new URL(args.url); url.pathname = url.pathname.replace(/v0_74\.html$/, 'v0_' + edition + '.html');
    const response = await page.goto(url.href, { waitUntil: 'domcontentloaded' });
    assert.equal(response?.status(), 200);
    await ready(edition);
    return { url: page.url(), title: await page.title(), save: await page.evaluate(() => window.__SOMA_V37_SAVE__.getStatus()) };
  }
  async function enterCampaign() {
    await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click();
    await page.waitForFunction(() => zone?.v52District && zone.static && zone.v68Architecture?.buildings > 0 && paused === false);
    return page.evaluate(() => ({ zone: zone.id, buildings: zone.v68Architecture.buildings, actors: zone.actors.length,
      webgl2: renderer.gl instanceof WebGL2RenderingContext, linked: renderer.gl.getProgramParameter(renderer.p, renderer.gl.LINK_STATUS) }));
  }
  async function activateBarrier() {
    await page.keyboard.press('Shift+F1');
    await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
    const before = await page.evaluate(() => window.__SOMA_V70__.snapshot());
    await page.locator('#v70-tactics [data-v70-ability="barrier"]').click();
    const after = await page.evaluate(() => { paused = true; return window.__SOMA_V70__.snapshot(); });
    assert(after.active.barrier > 0 && after.barrierRemaining > 0, 'A real Rempart must be active before transfer.');
    assert.equal(after.persisted.stats.barrier, before.persisted.stats.barrier + 1);
    assert.equal(after.persisted.stats.activations, before.persisted.stats.activations + 1);
    return { before, after };
  }
  try {
    const { chromium } = require('playwright');
    browser = await chromium.launch({ headless: true, ...(args.chromium ? { executablePath: args.chromium } : {}),
      args: ['--no-sandbox', '--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    report.environment.browser = browser.version();
    report.environment.playwright = require('playwright/package.json').version;
    for (const historical of [70, 71, 73]) {
      let exported, expected, activeSource;
      await step('v' + historical + '-load-real-page', () => openEdition(historical));
      await step('v' + historical + '-populate-real-progress', async () => {
        const scene = await enterCampaign();
        assert(scene.webgl2 && scene.linked && scene.buildings > 0);
        const conversation = await page.evaluate(() => {
          const actor = zone.actors.find(q => !q.nightActorId && !q.police && !q.characterId && typeof q.id === 'string');
          if (!actor) throw Error('No existing generic civilian is available in the real loaded scene.');
          const previous = state.v67.conversations[actor.id] || 0;
          npcDialogue(actor);
          const after = state.v67.conversations[actor.id];
          closeModals();
          return { id: actor.id, name: actor.name || actor.role || null, previous, after };
        });
        assert.equal(conversation.after, conversation.previous + 1);
        activeSource = await activateBarrier();
        await screenshot('v' + historical + '-active-before-export');
        return { scene, conversation, active: activeSource };
      });
      await step('v' + historical + '-download-authentic-grouped-export', async () => {
        await page.evaluate(() => window.__SOMA_GROUP64__.open());
        const downloadEvent = page.waitForEvent('download');
        await page.locator('#v64-group-export').click();
        const download = await downloadEvent;
        const filename = 'grouped-save-v' + historical + '.json';
        await download.saveAs(path.join(output, filename));
        exported = await fs.readFile(path.join(output, filename), 'utf8');
        const checked = await page.evaluate(text => {
          const group = window.__SOMA_GROUP64__.validate(text), campaign = JSON.parse(group.payload.campaign);
          return { summary: group.summary, campaignSchema: campaign.schema, core: campaign.payload.core,
            deck: group.payload.modules[42].value.cyberdeck, module42Key: group.payload.modules[42].key,
            modules: Object.keys(group.payload.modules), sourcePackSHA256: group.payload.sourcePackSHA256,
            activeAtExport: window.__SOMA_V70__.snapshot() };
        }, exported);
        expected = await page.evaluate(snapshot);
        assert(Object.keys(expected.v67.conversations).length > 0);
        assert(checked.activeAtExport.active.barrier > 0 && checked.activeAtExport.barrierRemaining > 0);
        assert.deepEqual(checked.core.v70, expected.v70);
        assert.deepEqual(checked.deck, expected.deck);
        assert.equal(checked.module42Key, expected.module42Key);
        assert(expected.v70.cooldowns.barrier > 0 && expected.v70.stats.barrier > 0);
        assert.deepEqual(Object.keys(checked.core.v70).sort(), ['cooldowns', 'schema', 'selected', 'stats', 'trace']);
        assert.deepEqual(expected.futureDomains, []);
        assert.equal(checked.summary.modules, 11);
        await context.close(); context = null; page = null;
        return { file: filename, bytes: Buffer.byteLength(exported), sha256: sha256(exported), suggestedFilename: download.suggestedFilename(),
          summary: checked.summary, campaignSchema: checked.campaignSchema, sourcePackSHA256: checked.sourcePackSHA256,
          sourceOwner: { campaign: expected.saveKey, augmentation: 'core.v70', cyberdeck: expected.module42Key },
          activeAtExport: checked.activeAtExport, expected };
      });
      await step('v' + historical + '-to-v74-load-isolated-target', async () => {
        const initial = await openEdition(74), scene = await enterCampaign(), active = await activateBarrier();
        assert(scene.webgl2 && scene.linked);
        const mutation = await page.evaluate(() => { const before = state.credits; state.credits += 17; return { before, after: state.credits }; });
        assert.equal(mutation.after, mutation.before + 17);
        return { initial, scene, active, mutation };
      });
      await step('v' + historical + '-to-v74-real-grouped-import', async () => {
        const result = await page.evaluate(text => window.__SOMA_GROUP64__.importText(text, true), exported);
        assert.deepEqual(result, { ok: true, modules: 11 });
        const actual = await page.evaluate(snapshot);
        assertRestored(actual, expected, 'v' + historical + ' import');
        await screenshot('v' + historical + '-imported-v74');
        return { result, actual, districtVisitsBefore: expected.v67.districtVisits, districtVisitsAfter: actual.v67.districtVisits };
      });
      await step('v' + historical + '-to-v74-reject-invalid-domains-without-write', async () => {
        const cases = await page.evaluate(async text => {
          const C = window.__SOMA_GROUP64_CORE__, G = window.__SOMA_GROUP64__, P = window.__SOMA_V37_SAVE__;
          P.flush();
          const storage = () => Object.fromEntries(Object.keys(localStorage).sort().map(key => [key, localStorage.getItem(key)]));
          const differences = (a, b, prefix = '') => {
            if (Object.is(a, b)) return [];
            if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return [{ path: prefix, before: a, after: b }];
            return [...new Set([...Object.keys(a), ...Object.keys(b)])].sort().flatMap(key => differences(a[key], b[key], prefix + '.' + key));
          };
          const capture = () => ({ storage: storage(), core: P.snapshot().payload.core, deck: JSON.parse(JSON.stringify(window.__SOMA_V42__.state().cyberdeck)) });
          const comparable = value => ({ ...value, core: { ...value.core, updatedAt: '[snapshotSave read time]' } });
          const noOperationBefore = capture(), noOperationAfter = capture();
          const noOperation = { differences: differences(noOperationBefore, noOperationAfter),
            unchangedExceptReadTimestamp: JSON.stringify(comparable(noOperationBefore)) === JSON.stringify(comparable(noOperationAfter)),
            storedBytesUnchanged: JSON.stringify(noOperationBefore.storage) === JSON.stringify(noOperationAfter.storage) };
          const edits = [
            ['active-buff-in-persistent-v70', core => { core.v70.active = { scan: 0, barrier: 4, focus: 0 }; }],
            ['out-of-bounds-persistent-cooldown', core => { core.v70.cooldowns.barrier = 24.001; }],
            ['new-unowned-core-v74-domain', core => { core.v74 = {}; }],
          ];
          const results = [];
          for (const [name, edit] of edits) {
            const grouped = C.decode(text), campaign = JSON.parse(grouped.campaign);
            edit(campaign.payload.core);
            campaign.checksum = C.hash(JSON.stringify(campaign.payload));
            grouped.campaign = JSON.stringify(campaign);
            const invalid = C.encode(grouped);
            const before = capture();
            let rejection = null;
            try { await G.importText(invalid, true); } catch (error) { rejection = String(error.message || error); }
            const after = capture();
            results.push({ name, rejection, unchanged: JSON.stringify(comparable(before)) === JSON.stringify(comparable(after)),
              differences: differences(before, after),
              storedBytesUnchanged: JSON.stringify(before.storage) === JSON.stringify(after.storage),
              snapshotReadTimes: { before: before.core.updatedAt, after: after.core.updatedAt,
                valid: [before.core.updatedAt, after.core.updatedAt].every(value => typeof value === 'string' && Number.isFinite(Date.parse(value))) },
              repairedOuterChecksum: C.decode(invalid).campaign === grouped.campaign,
              repairedCampaignChecksum: campaign.checksum === C.hash(JSON.stringify(campaign.payload)) });
          }
          return { noOperation, cases: results };
        }, exported);
        report.invalidImportCases ??= [];
        report.invalidImportCases.push({ historical, cases });
        assert(cases.noOperation.unchangedExceptReadTimestamp && cases.noOperation.storedBytesUnchanged, 'No-operation snapshot control changed authoritative data or storage.');
        assert(cases.noOperation.differences.every(item => item.path === '.core.updatedAt'), 'Snapshot read changed more than its generated timestamp.');
        for (const test of cases.cases) {
          assert(test.rejection, test.name + ': invalid grouped import was accepted.');
          assert.match(test.rejection, test.name === 'new-unowned-core-v74-domain' ? /incompatible/ : /Personnage\.v70/);
          assert(test.unchanged, test.name + ': rejection changed storage or authoritative state.');
          assert(test.storedBytesUnchanged, test.name + ': rejection changed stored bytes.');
          assert(test.snapshotReadTimes.valid, test.name + ': snapshot read timestamp is malformed.');
          assert(test.differences.every(item => item.path === '.core.updatedAt'), test.name + ': rejection changed more than the snapshot read timestamp.');
          assert(test.repairedOuterChecksum && test.repairedCampaignChecksum, test.name + ': only corruption was tested.');
        }
        assertRestored(await page.evaluate(snapshot), expected, 'After invalid v' + historical + ' derivatives');
        return cases;
      });
      await step('v' + historical + '-to-v74-reload-persisted-continuity', async () => {
        await page.reload({ waitUntil: 'domcontentloaded' });
        await ready(74);
        await page.evaluate(() => { paused = true; });
        const actual = await page.evaluate(snapshot);
        assertRestored(actual, expected, 'v' + historical + ' reload');
        const stored = await page.evaluate(key => JSON.parse(localStorage.getItem(key)), actual.saveKey);
        assert.deepEqual(stored.payload.core.v70, expected.v70);
        assert.equal(stored.payload.core.credits, expected.credits);
        return { actual, storedCampaignSchema: stored.schema, storedV70: stored.payload.core.v70, districtVisitsAfter: actual.v67.districtVisits };
      });
      await context.close(); context = null; page = null;
    }
    await step('browser-errors', async () => {
      assert.deepEqual(report.pageErrors, [], 'JavaScript errors were observed.');
      assert.deepEqual(report.consoleErrors, [], 'Console errors were observed.');
      assert.deepEqual(report.httpErrors, [], 'HTTP errors were observed.');
      assert.deepEqual(report.requestFailures, [], 'Requests failed.');
      return { pageErrors: 0, consoleErrors: 0, httpErrors: 0, requestFailures: 0, consoleWarnings: report.consoleWarnings.length };
    });
    report.passed = true;
  } catch (error) {
    failure = error; report.failure = errorRecord(error);
    if (page) { try { await screenshot('failure-' + currentStep); } catch (captureError) { report.captureFailure = errorRecord(captureError); } }
  } finally {
    if (context) { try { await context.close(); } catch (error) { report.cleanupError = errorRecord(error); } }
    if (browser) { try { await browser.close(); } catch (error) { report.cleanupError = errorRecord(error); } }
    if (report.cleanupError) report.passed = false;
    report.provenanceFinished = await sourceEvidence(__filename);
    report.sourceSetUnchanged = report.provenance.aggregateSHA256 === report.provenanceFinished.aggregateSHA256;
    report.finishedAt = new Date().toISOString();
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  }
  process.stdout.write(JSON.stringify({ passed: report.passed, report: path.join(output, 'report.json'), steps: report.steps.length }) + '\n');
  if (failure || !report.passed || report.cleanupError) process.exitCode = 1;
}
main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
