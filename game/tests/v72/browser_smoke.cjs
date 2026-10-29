#!/usr/bin/env node
'use strict';

/** Browser integration smoke for the built v0.72 campaign and independent viewer.
 * Run against a prepared local server, in a fresh non-persistent browser context.
 * This does not certify a campaign playthrough, combat AI or metropolitan coverage.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');

function options(argv) {
  const result = {
    url: 'http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_72.html',
    chromium: null,
    output: null,
    timeout: 90000,
  };
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (flag === '--help' || flag === '-h') {
      process.stdout.write('Usage: node game/tests/v72/browser_smoke.cjs [--url URL] [--chromium PATH] [--output DIRECTORY] [--timeout MILLISECONDS]\n');
      return null;
    }
    if (!['--url', '--chromium', '--output', '--timeout'].includes(flag)) throw Error('Unknown option: ' + flag);
    const value = argv[++i];
    if (!value || value.startsWith('--')) throw Error('Missing value for ' + flag);
    result[flag.slice(2)] = flag === '--timeout' ? Number(value) : value;
  }
  const url = new URL(result.url);
  assert(['http:', 'https:'].includes(url.protocol), '--url must use HTTP or HTTPS.');
  assert(Number.isInteger(result.timeout) && result.timeout >= 5000 && result.timeout <= 300000,
    '--timeout must be between 5000 and 300000 ms.');
  return result;
}

function errorRecord(error) {
  return { name: error?.name || 'Error', message: String(error?.message || error), stack: String(error?.stack || '').slice(0, 10000) };
}

async function deadline(promise, milliseconds, label) {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(Error(label + ' exceeded ' + milliseconds + ' ms.')), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
}

// Serialized by Playwright into the real campaign page; no production API is replaced.
function campaignSnapshot() {
  const clone = value => JSON.parse(JSON.stringify(value));
  const saver = window.__SOMA_V37_SAVE__;
  const envelope = saver.snapshot();
  saver.validate(envelope);
  return {
    saveKey: saver.key,
    status: saver.getStatus(),
    credits: state.credits,
    zone: state.zone,
    v67Schema: state.v67?.schema,
    conversations: clone(state.v67?.conversations || {}),
    v70: clone(state.v70),
    augmentation: window.__SOMA_V70__.snapshot(),
    radio: window.__SOMA_CONTACT_SHARING72__.snapshot(),
    netrunner: window.__SOMA_NETRUNNER72__.snapshot(),
    savedV70: clone(envelope.payload.core.v70),
    hasV71Domain: Object.hasOwn(envelope.payload.core, 'v71'),
    hasV72Domain: Object.hasOwn(envelope.payload.core, 'v72'),
  };
}

function assertRestored(actual, expected, label) {
  assert(actual.status.ready && !actual.status.blocked, label + ': campaign save is unavailable.');
  assert.equal(actual.credits, expected.credits, label + ': credits changed.');
  assert.equal(actual.zone, expected.zone, label + ': campaign location changed.');
  assert.equal(actual.v67Schema, 'soma-v67/1');
  assert.deepEqual(actual.conversations, expected.conversations, label + ': conversation progress changed.');
  assert.deepEqual(actual.v70, expected.v70, label + ': persisted cooldowns/counters changed.');
  assert.deepEqual(actual.savedV70, expected.v70, label + ': actual serializer differs from runtime state.');
  assert.deepEqual(actual.augmentation.persisted, expected.v70, label + ': augmentation owner differs.');
  assert(Object.values(actual.augmentation.active).every(value => value === 0), label + ': active buff survived restoration.');
  assert.equal(actual.augmentation.barrierRemaining, 0, label + ': temporary protection survived restoration.');
  assert.equal(actual.radio.contactCount, 0, label + ': radio contacts survived restoration.');
  assert.equal(actual.netrunner.activeChannels, 0, label + ': netrunner preparation survived restoration.');
  assert.equal(actual.hasV71Domain, false);
  assert.equal(actual.hasV72Domain, false);
}

async function main() {
  const args = options(process.argv.slice(2));
  if (!args) return;
  const output = args.output ? path.resolve(args.output) : await fs.mkdtemp(path.join(os.tmpdir(), 'massilia-v72-smoke-'));
  await fs.mkdir(output, { recursive: true });
  const report = {
    schema: 'soma/browser-smoke/72/1',
    version: '0.72.0',
    startedAt: new Date().toISOString(),
    url: args.url,
    output,
    passed: false,
    environment: { headless: true, freshBrowserContext: true, viewport: { width: 1440, height: 1000 }, softwareWebGLRequested: true },
    fixtures: [
      'Private browser storage starts empty; no user profile, route interception or production API mock is used.',
      'After a real Cortex activation, the smoke sets paused=true to compare serialized timers without elapsed gameplay time.',
      'Credits are temporarily increased by 17 solely to prove that the real grouped import restores the exported value.',
    ],
    limits: [
      'No long physical traversal, campaign completion, manual combat observation or performance certification.',
      'The persisted v70 domain used by v70/v71 is exercised in v72; historical v70/v71 pages are not played or imported separately.',
      'A live Cortex buff is populated before import; radio/netrunner are checked empty afterward, without injecting synthetic enemies or claiming a live combat reset.',
      'Inspectors use the actual initial rendered view. Empty, occluded or budget-limited results are reported as such, not as successful object selection.',
      'Only installed data and the initial streamed scene are observed; 92 destinations do not prove complete metropolitan or 1:1 architectural coverage.',
    ],
    steps: [],
    screenshots: [],
    pageErrors: [],
    consoleErrors: [],
    consoleWarnings: [],
    httpErrors: [],
    requestFailures: [],
    requests: { total: 0, responsesByStatus: {} },
  };
  let browser, context, page, currentStep = 'launch', navigating = false, failure = null;
  let expected, saveKey, viewerMetadata, viewerResult, viewerStorage;
  const record = (array, value) => {
    if (array.length < 200) array.push({ step: currentStep, ...value });
    else report.eventOverflow = true;
  };
  async function step(name, run) {
    currentStep = name;
    const item = { name, status: 'running', startedAt: new Date().toISOString() };
    report.steps.push(item);
    process.stderr.write('[v72 smoke] ' + name + '\n');
    try {
      item.observation = await deadline(Promise.resolve().then(run), args.timeout, name);
      item.status = 'passed';
      return item.observation;
    } catch (error) { item.status = 'failed'; item.error = errorRecord(error); throw error; }
    finally { item.finishedAt = new Date().toISOString(); }
  }
  async function screenshot(name) {
    const filename = name + '.png';
    await page.screenshot({ path: path.join(output, filename), timeout: args.timeout });
    report.screenshots.push(filename);
  }
  async function campaignReady() {
    await page.waitForFunction(() => window.__SOMA_V72__?.ready === true && window.__SOMA_V71__ &&
      window.__SOMA_V70__?.ready === true && window.__SOMA_GROUP64__?.ready === true &&
      window.__SOMA_TERRAIN56__?.grid && document.getElementById('v69-metropole-entry'), null, { timeout: args.timeout });
    assert.match(await page.title(), /SOMA\/\/MASSILIA 0\.72.*Marseille augmentée/);
  }
  async function storage() {
    return page.evaluate(() => Object.fromEntries(Object.keys(localStorage).sort().map(key => [key, localStorage.getItem(key)])));
  }
  async function navigate(action, expectedURL) {
    navigating = true;
    try {
      await Promise.all([page.waitForURL(expectedURL, { waitUntil: 'domcontentloaded', timeout: args.timeout }), action()]);
    } finally { navigating = false; }
  }

  try {
    const { chromium } = require('playwright');
    browser = await chromium.launch({
      headless: true,
      ...(args.chromium ? { executablePath: args.chromium } : {}),
      args: ['--no-sandbox', '--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    });
    report.environment.browser = browser.version();
    report.environment.playwright = require('playwright/package.json').version;
    context = await browser.newContext({ viewport: report.environment.viewport, locale: 'fr-FR', acceptDownloads: true });
    page = await context.newPage();
    page.setDefaultTimeout(args.timeout);
    page.setDefaultNavigationTimeout(args.timeout);
    page.on('pageerror', error => record(report.pageErrors, errorRecord(error)));
    page.on('console', message => {
      const entry = { text: message.text().slice(0, 6000), location: message.location() };
      if (message.type() === 'error') record(report.consoleErrors, entry);
      if (message.type() === 'warning') record(report.consoleWarnings, entry);
    });
    page.on('request', () => { report.requests.total++; });
    page.on('response', response => {
      const status = response.status();
      report.requests.responsesByStatus[status] = (report.requests.responsesByStatus[status] || 0) + 1;
      if (status >= 400) record(report.httpErrors, { status, url: response.url(), resourceType: response.request().resourceType() });
    });
    page.on('requestfailed', request => record(report.requestFailures, {
      url: request.url(), resourceType: request.resourceType(), error: request.failure()?.errorText, duringNavigation: navigating,
    }));

    await step('load-current-campaign', async () => {
      const response = await page.goto(args.url, { waitUntil: 'domcontentloaded' });
      assert.equal(response?.status(), 200, 'Campaign HTML must be served successfully.');
      await campaignReady();
      const ready = await page.evaluate(() => ({ edition: window.__SOMA_V72__.snapshot(), save: window.__SOMA_V37_SAVE__.getStatus() }));
      assert(ready.save.ready && !ready.save.blocked, 'Fresh campaign must have a working save owner.');
      return { title: await page.title(), ...ready };
    });

    await step('enter-real-marseille', async () => {
      await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click();
      await page.waitForFunction(() => typeof zone !== 'undefined' && zone?.v52District && zone.static &&
        zone.v68Architecture?.buildings > 0 && paused === false);
      const street = await page.evaluate(() => ({
        zone: zone.id, buildings: zone.v68Architecture.buildings, roads: zone.roads.length, size: [zone.w, zone.h],
        vectorSource: window.__SOMA_V54__.snapshot().source.sha256, terrainSource: window.__SOMA_TERRAIN56__.pack.sha256,
        webgl2: renderer.gl instanceof WebGL2RenderingContext,
        shaderLinked: renderer.gl.getProgramParameter(renderer.p, renderer.gl.LINK_STATUS),
        webglContextLost: renderer.gl.isContextLost(),
      }));
      assert(street.buildings > 0 && street.roads > 0);
      assert.deepEqual(street.size, [250, 250]);
      assert.equal(street.vectorSource, '0d16c8cd7c77945b22cb0a018f19a7d0bd1b3a2cbf05c137fa62e3aa8fd56d82');
      assert.equal(street.terrainSource, '38eadcbdf00a64384e00923a85ce9886ec4d9a420d610dc9ccfd4449c41f344b');
      assert(street.webgl2 && street.shaderLinked && !street.webglContextLost, 'Actual campaign WebGL2 shader must link.');
      await screenshot('01-campaign-real-marseille');
      return street;
    });

    await step('cortex-keyboard-and-visible-controls', async () => {
      await page.keyboard.press('Shift+F1');
      await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
      const panel = await page.locator('#v70-tactics').evaluate(node => ({
        title: node.querySelector('h2').textContent, cards: node.querySelectorAll('[data-v70-ability]').length,
        energy: node.querySelector('[data-v70-deck]').textContent, paused,
      }));
      assert.equal(panel.title, 'Cortex tactique');
      assert.equal(panel.cards, 3);
      assert.match(panel.energy, /Cyberdeck\s+\d+/);
      assert.equal(panel.paused, true);
      await screenshot('02-cortex');
      await page.locator('#v70-tactics [data-v70-close]').click();
      await page.waitForFunction(() => !paused && !document.getElementById('v70-tactics').classList.contains('open'));
      return { shortcut: 'Shift+F1', closeButtonReturnedToGame: true, ...panel };
    });

    await step('grouped-save-export-import', async () => {
      await page.keyboard.press('Shift+F1');
      await page.locator('#v70-tactics.open').waitFor({ state: 'visible' });
      const before = await page.evaluate(() => ({ ...window.__SOMA_V70__.snapshot(), activationCost: window.__SOMA_AUG70_CORE__.ABILITIES.barrier.cost }));
      assert(before.energy >= before.activationCost, 'Fresh cyberdeck must afford one real Rempart activation.');
      await page.locator('#v70-tactics [data-v70-ability="barrier"]').click();
      const active = await page.evaluate(() => { paused = true; return window.__SOMA_V70__.snapshot(); });
      assert(active.active.barrier > 0 && active.barrierRemaining > 0, 'The real Cortex button must activate Rempart before export.');
      assert.equal(active.persisted.stats.barrier, before.persisted.stats.barrier + 1);
      assert.equal(active.persisted.stats.activations, before.persisted.stats.activations + 1);
      const exported = await page.evaluate(() => {
        const G = window.__SOMA_GROUP64__, text = G.exportText(), checked = G.validate(text);
        const campaign = JSON.parse(checked.payload.campaign), core = campaign.payload.core;
        return { text, summary: checked.summary, campaignSchema: campaign.schema, expected: {
          credits: core.credits, zone: core.zone, v70: core.v70, conversations: core.v67.conversations,
        }, temporaryFieldsSerialized: ['active', 'barrierRemaining'].filter(key => Object.hasOwn(core.v70, key)),
        hasV71Domain: Object.hasOwn(core, 'v71'), hasV72Domain: Object.hasOwn(core, 'v72') };
      });
      expected = exported.expected;
      assert(expected.v70.cooldowns.barrier > 0 && expected.v70.stats.barrier > 0);
      assert.deepEqual(exported.temporaryFieldsSerialized, []);
      assert.equal(exported.hasV71Domain, false);
      assert.equal(exported.hasV72Domain, false);
      const exportPath = path.join(output, 'grouped-save-v72.json');
      await fs.writeFile(exportPath, exported.text, 'utf8');
      const restored = await page.evaluate(async text => {
        const previousCredits = state.credits;
        state.credits += 17;
        const mutatedCredits = state.credits;
        const result = await window.__SOMA_GROUP64__.importText(text, true);
        return { result, previousCredits, mutatedCredits };
      }, exported.text);
      assert.equal(restored.mutatedCredits, restored.previousCredits + 17);
      assert.equal(restored.result.ok, true, JSON.stringify(restored.result));
      assert.equal(restored.result.modules, exported.summary.modules);
      const after = await page.evaluate(campaignSnapshot);
      assertRestored(after, expected, 'Grouped import');
      saveKey = after.saveKey;
      return { exportFile: path.basename(exportPath), bytes: Buffer.byteLength(exported.text),
        sha256: crypto.createHash('sha256').update(exported.text).digest('hex'),
        campaignSchema: exported.campaignSchema, modules: exported.summary.modules,
        activeBeforeImport: active.active, persisted: expected.v70, import: restored, after };
    });

    await step('reload-restores-continuity', async () => {
      navigating = true;
      try { await page.reload({ waitUntil: 'domcontentloaded' }); } finally { navigating = false; }
      await campaignReady();
      await page.evaluate(() => { paused = true; });
      const reloaded = await page.evaluate(campaignSnapshot);
      assertRestored(reloaded, expected, 'Reload');
      return reloaded;
    });

    await step('open-real-v72-flyover-button', async () => {
      await page.locator('#v69-metropole-entry').waitFor({ state: 'visible' });
      await navigate(() => page.locator('#v69-metropole-entry').click(), /\/metropole-viewer-v72\.html(?:[?#]|$)/);
      assert.match(await page.title(), /0\.72.*Survol/);
      await page.waitForFunction(() => window.__SOMA_METRO_VIEWER__ && window.__SOMA_ARCHITECTURE71_VIEWER__ && window.__SOMA_ROAD_INSPECTION72_VIEWER__);
      await page.waitForFunction(() => {
        const s = window.__SOMA_METRO_VIEWER__.snapshot();
        return s.resident > 0 && s.pendingGeometry === 0 && s.renderedFrames > 1 && s.buildings > 0 && s.roadTriangles > 0;
      });
      viewerMetadata = await page.evaluate(() => {
        const data = JSON.parse(document.getElementById('soma-viewer-data').textContent);
        return { version: data.version, defaultWorld: data.defaultWorld, fallbackWorld: data.fallbackWorld,
          communes: data.territory.communes.length, returnToGame: data.returnToGame };
      });
      viewerResult = await page.evaluate(() => ({ ...window.__SOMA_METRO_VIEWER__.snapshot(), coverageText: document.getElementById('coverage').textContent }));
      assert.equal(viewerMetadata.version, '0.72.0');
      assert.equal(viewerMetadata.communes, 92);
      assert.equal(viewerMetadata.returnToGame, 'SOMA_MASSILIA_URBAIN_v0_72.html');
      assert.equal(viewerResult.campaignPersistenceLoaded, false);
      assert.equal(viewerResult.webglError, 0);
      assert.deepEqual(viewerResult.webglErrors, []);
      assert.equal(viewerResult.buildFailures, 0);
      assert.deepEqual(viewerResult.errors, []);
      if (viewerResult.mode === 'fallback-centre') {
        assert.match(viewerResult.coverageText, /Centre de Marseille.*carte partielle/);
        assert.equal(viewerResult.manifestURL, new URL(viewerMetadata.fallbackWorld, page.url()).href);
      }
      // The campaign's pagehide handler saves a checkpoint on departure. Take the
      // byte baseline after arrival, then prove the viewer itself never changes it.
      viewerStorage = await storage();
      const saved = JSON.parse(viewerStorage[saveKey]);
      assert.deepEqual(saved.payload.core.v70, expected.v70);
      assert.equal(saved.payload.core.credits, expected.credits);
      await screenshot('03-flyover-installed-data');
      return { metadata: viewerMetadata, scene: viewerResult, scope: 'Initial installed scene only; no complete-metropolis claim.' };
    });

    for (const inspection of [
      { name: 'architecture', open: '#architecture71-open', dialog: '#architecture71-dialog', key: 'i', api: '__SOMA_ARCHITECTURE71_VIEWER__', status: '#architecture71-status', success: 'building' },
      { name: 'road', open: '#road72-open', dialog: '#road72-dialog', key: 'j', api: '__SOMA_ROAD_INSPECTION72_VIEWER__', status: '#road72-status', success: 'road' },
    ]) {
      await step('inspect-' + inspection.name + '-in-rendered-scene', async () => {
        await page.locator(inspection.open).click();
        await page.locator(inspection.dialog).waitFor({ state: 'visible' });
        await page.waitForFunction(api => window[api].snapshot().phase === 'ready', inspection.api);
        const result = await page.evaluate(api => window[api].snapshot(), inspection.api);
        assert(result.open && result.result, 'Inspector must return a result from the real rendered scene.');
        assert([inspection.success, 'empty', 'occluded', 'budget'].includes(result.result.status));
        assert(result.result.testedTriangles > 0, 'Inspector must examine actual streamed geometry.');
        const statusText = await page.locator(inspection.status).textContent();
        assert(statusText.trim().length > 0);
        await screenshot('04-inspector-' + inspection.name);
        await page.keyboard.press(inspection.key);
        await page.waitForFunction(api => window[api].snapshot().phase === 'closed', inspection.api);
        await page.locator(inspection.dialog).waitFor({ state: 'hidden' });
        return { statusText, selectionObserved: result.result.status === inspection.success, actualResult: result.result,
          openedByRealButton: true, closedByShortcut: inspection.key.toUpperCase() };
      });
    }

    await step('flyover-keeps-campaign-storage-intact', async () => {
      assert.deepEqual(await storage(), viewerStorage, 'Flyover or inspectors changed campaign storage.');
      const scene = await page.evaluate(() => window.__SOMA_METRO_VIEWER__.snapshot());
      assert.equal(scene.buildFailures, 0);
      assert.deepEqual(scene.errors, []);
      assert.deepEqual(scene.webglErrors, []);
      return { storageKeysCompared: Object.keys(viewerStorage).length, exactStorageUnchanged: true, mode: scene.mode };
    });

    await step('return-link-restores-campaign', async () => {
      assert.equal(await page.locator('#return-game').getAttribute('href'), 'SOMA_MASSILIA_URBAIN_v0_72.html');
      await navigate(() => page.locator('#return-game').click(), /\/SOMA_MASSILIA_URBAIN_v0_72\.html(?:[?#]|$)/);
      await campaignReady();
      await page.evaluate(() => { paused = true; });
      const returned = await page.evaluate(campaignSnapshot);
      assertRestored(returned, expected, 'Return from flyover');
      return returned;
    });

    await step('runtime-and-network-errors', async () => {
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)))));
      const optionalURL = viewerMetadata ? new URL(viewerMetadata.defaultWorld, new URL('metropole-viewer-v72.html', args.url)).href : null;
      const fallbackObserved = viewerResult?.mode === 'fallback-centre';
      for (const entry of report.httpErrors) {
        entry.expected = fallbackObserved && entry.url === optionalURL && entry.status === 404;
        if (entry.expected) entry.reason = 'Optional metropolitan manifest absent; real centre fallback successfully rendered.';
      }
      for (const entry of report.consoleErrors) {
        entry.expected = fallbackObserved && entry.location.url === optionalURL && /404/.test(entry.text) &&
          report.httpErrors.some(http => http.expected && http.url === entry.location.url);
        if (entry.expected) entry.reason = 'Browser resource error for the same observed optional-manifest 404.';
      }
      for (const entry of report.requestFailures) {
        // viewer69 readBytes() explicitly cancels response.body on !response.ok
        // before throwing its HTTP status. Chromium can then report ERR_ABORTED
        // for that fetch. Accept only the logged optional-manifest 404 whose
        // actual centre fallback was rendered; an arbitrary aborted fetch fails.
        const optionalBodyCancelled = fallbackObserved && entry.url === optionalURL &&
          entry.resourceType === 'fetch' && entry.error === 'net::ERR_ABORTED' &&
          report.httpErrors.some(http => http.expected && http.status === 404 &&
            http.url === entry.url && http.resourceType === 'fetch' && http.step === entry.step);
        const navigationCancelled = entry.duringNavigation && entry.resourceType !== 'document' && entry.error === 'net::ERR_ABORTED';
        entry.expected = optionalBodyCancelled || navigationCancelled;
        if (optionalBodyCancelled) {
          entry.expectedKind = 'optional-manifest-response-body-cancel';
          entry.reason = 'Viewer readBytes() cancelled the response body of the logged optional metropolitan manifest HTTP 404; the real centre fallback was successfully rendered.';
        } else if (navigationCancelled) {
          entry.expectedKind = 'navigation-resource-cancel';
          entry.reason = 'In-flight resource cancelled during an explicit page navigation.';
        }
      }
      assert.equal(report.eventOverflow, undefined, 'Error log overflowed; inspect the failing page.');
      assert.equal(report.pageErrors.length, 0, JSON.stringify(report.pageErrors));
      assert.deepEqual(report.httpErrors.filter(row => !row.expected), [], 'Unexpected HTTP failures.');
      assert.deepEqual(report.consoleErrors.filter(row => !row.expected), [], 'Unexpected console errors.');
      assert.deepEqual(report.requestFailures.filter(row => !row.expected), [], 'Unexpected network request failures.');
      return { pageErrors: report.pageErrors.length, optionalManifest404s: report.httpErrors.filter(row => row.expected).length,
        optionalManifestBodyCancellations: report.requestFailures.filter(row => row.expectedKind === 'optional-manifest-response-body-cancel').length,
        navigationAborts: report.requestFailures.filter(row => row.expectedKind === 'navigation-resource-cancel').length,
        warningsRecorded: report.consoleWarnings.length };
    });
    report.passed = true;
  } catch (error) {
    failure = error;
    report.failure = errorRecord(error);
    if (page && !page.isClosed()) {
      try { await deadline(screenshot('failure'), 15000, 'Failure screenshot'); }
      catch (captureError) { report.failureScreenshotError = errorRecord(captureError); }
    }
  } finally {
    currentStep = 'cleanup';
    navigating = true;
    try { await browser?.close(); } catch (closeError) { report.closeError = errorRecord(closeError); }
    report.finishedAt = new Date().toISOString();
    const reportPath = path.join(output, 'report.json');
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8');
    process.stdout.write(JSON.stringify({ passed: report.passed, report: reportPath, steps: report.steps.map(({ name, status }) => ({ name, status })),
      ...(failure ? { error: failure.message } : {}) }, null, 2) + '\n');
  }
  if (failure) process.exitCode = 1;
}

main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
