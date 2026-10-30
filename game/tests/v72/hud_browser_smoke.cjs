#!/usr/bin/env node
'use strict';

/** Responsive HUD smoke against the actual built v0.72 campaign.
 * Uses real menus in a private browser context; never activates an augmentation,
 * changes campaign state, injects an enemy, or substitutes a production API.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');

const TOLERANCE = 1;
const HUD_SLOTS = ['header', 'navigation', 'alerts', 'status', 'vitals', 'context', 'combat', 'footer'];
const HUD_PANELS = [
  '.hud .topbar', '.hud .stats', '.hud .weapon', '#level27', '#quick28', '#stance28',
  '#nightObjective', '#modeText', '#v34-launcher', '#v42-posture-hud', '#v42-city-hud',
  '#v43-cred', '#v43-weapon', '#v44-gps', '#v45-tracker', '#v52-hud',
  '#v54-attribution', '#terrain56-hud', '#v70-hud',
];
const VITAL_READOUTS = [{ text: 'healthText', bar: 'healthBar' }, { text: 'armorText', bar: 'armorBar' }];
const HUD_VIEWPORTS = [
  { width: 1920, height: 1080 }, { width: 1440, height: 1000 },
  { width: 1280, height: 720 }, { width: 1024, height: 768 },
  { width: 1440, height: 1000 },
];
const MENU_VIEWPORTS = [...HUD_VIEWPORTS.slice(0, 4), { width: 700, height: 800 }];

function options(argv) {
  const result = { url: 'http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_72.html', chromium: null, output: null, timeout: 90000 };
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (flag === '--help' || flag === '-h') {
      process.stdout.write('Usage: node game/tests/v72/hud_browser_smoke.cjs [--url URL] [--chromium PATH] [--output DIRECTORY] [--timeout MILLISECONDS]\n');
      return null;
    }
    if (!['--url', '--chromium', '--output', '--timeout'].includes(flag)) throw Error('Unknown option: ' + flag);
    const value = argv[++i];
    if (!value || value.startsWith('--')) throw Error('Missing value for ' + flag);
    result[flag.slice(2)] = flag === '--timeout' ? Number(value) : value;
  }
  assert(['http:', 'https:'].includes(new URL(result.url).protocol), '--url must use HTTP or HTTPS.');
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

// Playwright serializes this function into the real page. referenceNodes is a
// JSHandle to the mounted nodes, not a window global or a replacement renderer.
function layoutSnapshot({ selectors, slotNames, readouts, referenceNodes, masked }) {
  const hud = document.querySelector('.game > .hud');
  const layout = document.querySelector('.game > .hud > #v72-hud-layout');
  const viewport = { width: innerWidth, height: innerHeight };
  const label = element => element.id ? '#' + element.id : element.tagName.toLowerCase() +
    (typeof element.className === 'string' && element.className ? '.' + element.className.trim().split(/\s+/).join('.') : '');
  function cssVisible(element) {
    if (!element || !element.getClientRects().length) return false;
    const style = getComputedStyle(element), rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0 || ['hidden', 'collapse'].includes(style.visibility)) return false;
    // A child may explicitly override inherited visibility. Inspect its computed
    // value above, but opacity:0 and display:none on any ancestor conceal it.
    for (let current = element; current; current = current.parentElement) {
      const ancestor = getComputedStyle(current);
      if (ancestor.display === 'none' || Number(ancestor.opacity) === 0) return false;
    }
    return true;
  }
  function measure(element) {
    if (!element) return null;
    const style = getComputedStyle(element), rect = element.getBoundingClientRect();
    return {
      id: element.id, cssVisible: cssVisible(element), hiddenAttribute: element.hasAttribute('hidden'),
      display: style.display, visibility: style.visibility, opacity: style.opacity, pointerEvents: style.pointerEvents,
      rect: { x: rect.x, y: rect.y, left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height },
      clientWidth: element.clientWidth, scrollWidth: element.scrollWidth,
      clientHeight: element.clientHeight, scrollHeight: element.scrollHeight,
      overflowX: style.overflowX, overflowY: style.overflowY,
      text: (element.innerText || '').trim().slice(0, 200),
    };
  }
  const vitalReadouts = readouts.map(({ text, bar }) => {
    const element = document.getElementById(text), barElement = document.getElementById(bar)?.parentElement;
    const row = element?.closest('.row'), rowLabel = row?.firstElementChild;
    const rangeRects = [], lines = [];
    if (element) {
      const range = document.createRange();
      range.selectNodeContents(element);
      for (const rect of range.getClientRects()) {
        if (rect.width <= 0 || rect.height <= 0) continue;
        const fragment = { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height };
        rangeRects.push(fragment);
        // Several inline fragments can belong to one visual line. Distinct
        // vertical positions reveal wrapping even when scrollWidth fits.
        if (!lines.some(line => Math.abs(line.top - rect.top) <= 1)) lines.push({ top: rect.top, bottom: rect.bottom });
      }
    }
    return { selector: '#' + text, ...measure(element), text: (element?.textContent || '').trim(),
      rangeRects, lineCount: lines.length, lines, bar: measure(barElement), label: measure(rowLabel) };
  });
  const nodes = selectors.map(selector => document.querySelector(selector));
  const panels = selectors.map((selector, index) => ({
    selector, count: document.querySelectorAll(selector).length,
    inLayout: !!layout?.contains(nodes[index]),
    slot: nodes[index]?.closest('[data-v72-hud-slot]')?.getAttribute('data-v72-hud-slot') || null,
    sameMountedNode: referenceNodes ? referenceNodes[index] === nodes[index] : null,
    ...measure(nodes[index]),
  }));
  const intersections = [], nestedPanels = [];
  for (let i = 0; i < panels.length; i++) {
    for (let j = i + 1; j < panels.length; j++) {
      if (!nodes[i] || !nodes[j]) continue;
      if (nodes[i].contains(nodes[j]) || nodes[j].contains(nodes[i])) {
        nestedPanels.push([selectors[i], selectors[j]]);
        continue;
      }
      if (!panels[i].cssVisible || !panels[j].cssVisible) continue;
      const a = panels[i].rect, b = panels[j].rect;
      const width = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const height = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (width > 0 && height > 0) intersections.push({ a: selectors[i], b: selectors[j], width, height });
    }
  }
  const cortex = document.querySelector('#v70-tactics'), panel = cortex?.querySelector('.panel');
  const grid = cortex?.querySelector('.v70-grid');
  return {
    viewport, paused: !!paused, bodyMenuOpen: document.body.classList.contains('v34-menu-open'),
    openModals: Array.from(document.querySelectorAll('.modal.open'), node => node.id),
    document: { clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth },
    hud: measure(hud), layout: measure(layout), layoutCount: document.querySelectorAll('#v72-hud-layout').length,
    slots: slotNames.map(name => ({ name, count: layout?.querySelectorAll('[data-v72-hud-slot="' + name + '"]').length || 0 })),
    slotCount: layout?.querySelectorAll('[data-v72-hud-slot]').length || 0,
    panels, intersections, nestedPanels, vitalReadouts,
    visibleHudDescendants: masked && hud ? Array.from(hud.querySelectorAll('*')).filter(cssVisible).map(label) : null,
    cortex: {
      open: !!cortex?.classList.contains('open'), panel: measure(panel), grid: measure(grid),
      gridColumns: grid ? getComputedStyle(grid).gridTemplateColumns : null,
      buttons: Array.from(cortex?.querySelectorAll('[data-v70-ability]') || [], button => ({
        ability: button.getAttribute('data-v70-ability'), disabled: button.disabled, ...measure(button),
      })),
      close: measure(cortex?.querySelector('[data-v70-close]')),
    },
  };
}

// Compare only the requested owners while a real menu pauses simulation. Full
// envelopes contain timestamps and other data unrelated to responsive layout.
function pausedContinuity() {
  if (!paused) throw Error('Continuity comparison requires a real paused menu.');
  const saver = window.__SOMA_V37_SAVE__, envelope = saver.snapshot();
  saver.validate(envelope);
  return {
    credits: state.credits, zone: state.zone,
    coreV70: JSON.parse(JSON.stringify(envelope.payload.core.v70)),
    energy: window.__SOMA_V42__.state().cyberdeck.energy,
  };
}

function assertStructure(snapshot) {
  assert.equal(snapshot.layoutCount, 1, 'The current HUD layout must occur exactly once.');
  assert(snapshot.layout, '#v72-hud-layout must be a direct child of .game > .hud.');
  assert.equal(snapshot.slotCount, HUD_SLOTS.length, 'Unexpected or missing HUD slot.');
  for (const slot of snapshot.slots) assert.equal(slot.count, 1, 'HUD slot ' + slot.name + ' must occur exactly once.');
  for (const panel of snapshot.panels) {
    assert.equal(panel.count, 1, panel.selector + ': original panel must occur exactly once.');
    assert(panel.inLayout, panel.selector + ': original panel is outside the current HUD layout.');
    assert(HUD_SLOTS.includes(panel.slot), panel.selector + ': no declared layout slot.');
    assert.equal(panel.sameMountedNode, true, panel.selector + ': a resize or menu replaced the mounted node.');
  }
  assert.deepEqual(snapshot.nestedPanels, [], 'The independent required HUD panels must not contain each other.');
}

function contained(rect, viewport) {
  return rect && rect.width > 0 && rect.height > 0 &&
    rect.left >= -TOLERANCE && rect.top >= -TOLERANCE &&
    rect.right <= viewport.width + TOLERANCE && rect.bottom <= viewport.height + TOLERANCE;
}

function assertHud(snapshot) {
  assertStructure(snapshot);
  assert.equal(snapshot.paused, false, 'HUD measurements require active exploration.');
  assert.equal(snapshot.bodyMenuOpen, false, 'Menu class must clear on return to exploration.');
  assert.deepEqual(snapshot.openModals, [], 'A menu is still open during a HUD measurement.');
  const problems = [];
  for (const panel of snapshot.panels) {
    if (!panel.cssVisible) problems.push(panel.selector + ' is concealed.');
    if (!contained(panel.rect, snapshot.viewport)) problems.push(panel.selector + ' is outside the viewport.');
    if (panel.scrollWidth > panel.clientWidth + TOLERANCE) problems.push(panel.selector + ' has horizontal overflow.');
  }
  for (const readout of snapshot.vitalReadouts) {
    if (!readout.cssVisible || !readout.text) problems.push(readout.selector + ' has no visible value.');
    if (readout.lineCount !== 1) problems.push(readout.selector + ' uses ' + readout.lineCount + ' text lines instead of one.');
    for (const peer of ['bar', 'label']) {
      const adjacent = readout[peer];
      if (!adjacent?.cssVisible) { problems.push(readout.selector + ': adjacent ' + peer + ' is missing or concealed.'); continue; }
      for (const fragment of readout.rangeRects) {
        const width = Math.min(fragment.right, adjacent.rect.right) - Math.max(fragment.left, adjacent.rect.left);
        const height = Math.min(fragment.bottom, adjacent.rect.bottom) - Math.max(fragment.top, adjacent.rect.top);
        if (width > TOLERANCE && height > TOLERANCE) {
          problems.push(readout.selector + ' text overlaps its ' + peer + '.');
          break;
        }
      }
    }
  }
  for (const overlap of snapshot.intersections) {
    if (overlap.width > TOLERANCE && overlap.height > TOLERANCE)
      problems.push(overlap.a + ' overlaps ' + overlap.b + ' (' + overlap.width.toFixed(2) + ' × ' + overlap.height.toFixed(2) + ' px).');
  }
  if (snapshot.document.scrollWidth > snapshot.document.clientWidth + TOLERANCE) problems.push('The document has horizontal overflow.');
  assert.deepEqual(problems, [], 'Responsive HUD contract failed.');
}

function assertMasked(snapshot) {
  assertStructure(snapshot);
  assert(snapshot.openModals.length || snapshot.bodyMenuOpen, 'HUD concealment must be observed in a real menu state.');
  assert.equal(snapshot.hud.cssVisible, false, 'The HUD root is visible over a menu.');
  assert.equal(snapshot.layout.cssVisible, false, 'The HUD layout is visible over a menu.');
  assert.deepEqual(snapshot.visibleHudDescendants, [], 'A HUD descendant escapes menu concealment.');
}

function assertCortex(snapshot) {
  assertMasked(snapshot);
  assert.equal(snapshot.paused, true, 'The real Cortex must pause gameplay.');
  assert.deepEqual(snapshot.openModals, ['v70-tactics'], 'Cortex must be the only open modal.');
  const cortex = snapshot.cortex;
  assert(cortex.open && cortex.panel?.cssVisible, 'Cortex panel is not rendered.');
  assert(contained(cortex.panel.rect, snapshot.viewport), 'Cortex panel extends outside the viewport.');
  assert(cortex.panel.scrollWidth <= cortex.panel.clientWidth + TOLERANCE, 'Cortex panel has horizontal overflow.');
  assert(cortex.grid?.scrollWidth <= cortex.grid?.clientWidth + TOLERANCE, 'Cortex cards have horizontal overflow.');
  assert.deepEqual(cortex.buttons.map(button => button.ability).sort(), ['barrier', 'focus', 'scan']);
  assert(cortex.buttons.every(button => button.cssVisible), 'A Cortex ability was concealed.');
  assert(cortex.close?.cssVisible, 'The Cortex close button was concealed.');
  assert(snapshot.document.scrollWidth <= snapshot.document.clientWidth + TOLERANCE, 'The menu causes document horizontal overflow.');
}

async function main() {
  const args = options(process.argv.slice(2));
  if (!args) return;
  const output = args.output ? path.resolve(args.output) : await fs.mkdtemp(path.join(os.tmpdir(), 'massilia-v72-hud-smoke-'));
  await fs.mkdir(output, { recursive: true });
  const report = {
    schema: 'soma/hud-browser-smoke/72/1', version: '0.72.0', startedAt: new Date().toISOString(),
    url: args.url, output, passed: false,
    environment: { headless: true, freshBrowserContext: true, locale: 'fr-FR', softwareWebGLRequested: true,
      initialViewport: HUD_VIEWPORTS[0], hudViewports: HUD_VIEWPORTS, cortexViewports: [...MENU_VIEWPORTS, HUD_VIEWPORTS.at(-1)] },
    contract: { toleranceCSSPixels: TOLERANCE, slots: HUD_SLOTS, requiredPanels: HUD_PANELS,
      singleLineReadouts: VITAL_READOUTS.map(readout => '#' + readout.text) },
    method: [
      'Private browser storage starts empty; the actual campaign button and menu controls are used.',
      'No network interception, injected enemies, production API replacement or campaign-state write is used.',
      'No augmentation is activated. Credits, zone, core.v70 and cyberdeck energy are compared only during real menu pauses.',
      'CSS visibility, viewport containment, panel intersections and horizontal overflow are measured after two animation frames.',
      'Range.getClientRects() checks that health and armor values each occupy one text line without covering their bar or label.',
    ],
    limits: [
      'Only the initial real Marseille scene and the listed HUD panels are qualified; conditional combat, police and vehicle overlays are not activated.',
      '700 × 800 covers the Cortex menu and the inherited hidden-consumables rule only, not narrow-screen exploration or mobile playability.',
      'Large text is the existing dialogue option; HUD text scaling and focus-navigation redesign are outside this smoke.',
      'Mounted node identity is checked across resizes and menus; this is not an instrumentation of the earlier mounting process.',
      'No save import, full campaign, flyover, gamepad, hardware GPU performance or accessibility certification.',
    ],
    steps: [], hudMeasurements: [], cortexMeasurements: [], screenshots: [],
    pageErrors: [], consoleErrors: [], consoleWarnings: [], httpErrors: [], requestFailures: [],
    requests: { total: 0, responsesByStatus: {} },
  };
  let browser, context, page, referenceNodes, currentStep = 'launch', failure = null, observing = true;
  const record = (array, value) => {
    if (!observing) return;
    if (array.length < 200) array.push({ step: currentStep, ...value });
    else report.eventOverflow = true;
  };
  async function step(name, run) {
    currentStep = name;
    const item = { name, status: 'running', startedAt: new Date().toISOString() };
    report.steps.push(item);
    process.stderr.write('[v72 HUD smoke] ' + name + '\n');
    try {
      item.observation = await deadline(Promise.resolve().then(() => run(item)), args.timeout, name);
      item.status = 'passed';
    } catch (error) { item.status = 'failed'; item.error = errorRecord(error); throw error; }
    finally { item.finishedAt = new Date().toISOString(); }
  }
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)))));
  async function resize(viewport) { await page.setViewportSize(viewport); await settle(); }
  async function screenshot(name) {
    const filename = name + '.png';
    await page.screenshot({ path: path.join(output, filename), timeout: args.timeout });
    report.screenshots.push({ file: filename, viewport: page.viewportSize(), step: currentStep });
  }
  async function measure(masked) {
    return page.evaluate(layoutSnapshot, { selectors: HUD_PANELS, slotNames: HUD_SLOTS, readouts: VITAL_READOUTS, referenceNodes, masked });
  }
  async function resumed() {
    await page.waitForFunction(() => !paused && !document.querySelector('.modal.open') && !document.body.classList.contains('v34-menu-open'));
    await page.locator('#v70-hud').waitFor({ state: 'visible' });
    await settle();
  }
  async function observeHud(viewport, label, capture) {
    await step(label, async item => {
      await resize(viewport);
      const measured = await measure(false);
      item.observation = measured;
      report.hudMeasurements.push({ step: label, ...measured });
      assertHud(measured);
      if (capture) await screenshot(capture);
      return measured;
    });
  }
  async function observeCortex(viewport, label, expected, capture) {
    await step(label, async item => {
      await resize(viewport);
      const measured = await measure(true), continuity = await page.evaluate(pausedContinuity);
      item.observation = { layout: measured, continuity };
      report.cortexMeasurements.push({ step: label, ...measured });
      assertCortex(measured);
      assert.deepEqual(continuity, expected, 'A paused resize changed campaign resources or core.v70.');
      if (capture) await screenshot(capture);
      return { layout: measured, continuity };
    });
  }

  try {
    const { chromium } = require('playwright');
    browser = await chromium.launch({ headless: true, ...(args.chromium ? { executablePath: args.chromium } : {}),
      args: ['--no-sandbox', '--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    report.environment.browser = browser.version();
    report.environment.playwright = require('playwright/package.json').version;
    context = await browser.newContext({ viewport: report.environment.initialViewport, locale: 'fr-FR' });
    page = await context.newPage();
    page.setDefaultTimeout(args.timeout);
    page.setDefaultNavigationTimeout(args.timeout);
    page.on('pageerror', error => record(report.pageErrors, errorRecord(error)));
    page.on('console', message => {
      const entry = { text: message.text().slice(0, 6000), location: message.location() };
      if (message.type() === 'error') record(report.consoleErrors, entry);
      if (message.type() === 'warning') record(report.consoleWarnings, entry);
    });
    page.on('request', () => { if (observing) report.requests.total++; });
    page.on('response', response => {
      if (!observing) return;
      const status = response.status();
      report.requests.responsesByStatus[status] = (report.requests.responsesByStatus[status] || 0) + 1;
      if (status >= 400) record(report.httpErrors, { status, url: response.url(), resourceType: response.request().resourceType() });
    });
    page.on('requestfailed', request => record(report.requestFailures, {
      url: request.url(), resourceType: request.resourceType(), error: request.failure()?.errorText,
    }));

    await step('load-current-campaign', async () => {
      const response = await page.goto(args.url, { waitUntil: 'domcontentloaded' });
      assert.equal(response?.status(), 200, 'The actual campaign HTML must load successfully.');
      await page.waitForFunction(() => window.__SOMA_V72__?.ready === true && window.__SOMA_V70__?.ready === true &&
        window.__SOMA_HUD72__?.ready === true && window.__SOMA_V37_SAVE__?.getStatus?.().ready === true);
      await page.locator('.game > .hud > #v72-hud-layout[data-ready="true"]').waitFor({ state: 'attached' });
      assert.match(await page.title(), /SOMA\/\/MASSILIA 0\.72.*Marseille augmentée/);
      return { title: await page.title(), viewport: page.viewportSize() };
    });

    await step('enter-real-marseille', async () => {
      await page.getByRole('button', { name: 'Explorer Marseille réelle', exact: true }).click();
      await page.waitForFunction(() => typeof zone !== 'undefined' && zone?.v52District && zone.static && zone.v68Architecture?.buildings > 0 && !paused);
      await resumed();
      referenceNodes = await page.evaluateHandle(selectors => selectors.map(selector => document.querySelector(selector)), HUD_PANELS);
      const scene = await page.evaluate(() => ({ zone: zone.id, buildings: zone.v68Architecture.buildings, roads: zone.roads.length,
        webgl2: renderer.gl instanceof WebGL2RenderingContext, contextLost: renderer.gl.isContextLost() }));
      assert(scene.buildings > 0 && scene.roads > 0 && scene.webgl2 && !scene.contextLost, 'The real street scene must be available.');
      return scene;
    });

    for (const [index, viewport] of HUD_VIEWPORTS.entries()) {
      const size = viewport.width + 'x' + viewport.height;
      const capture = viewport.width === 1280 || viewport.width === 1024 ? 'hud-' + size : null;
      await observeHud(viewport, 'hud-' + (index === HUD_VIEWPORTS.length - 1 ? 'return-' : '') + size, capture);
    }

    let pausedBaseline;
    await step('open-cortex-with-real-shortcut', async () => {
      await page.keyboard.press('Shift+F1');
      await page.locator('#v70-tactics.open .panel').waitFor({ state: 'visible' });
      await settle();
      pausedBaseline = await page.evaluate(pausedContinuity);
      assert(Number.isFinite(pausedBaseline.energy), 'The actual cyberdeck energy must be readable.');
      return { shortcut: 'Shift+F1', continuity: pausedBaseline };
    });
    for (const viewport of MENU_VIEWPORTS) {
      const size = viewport.width + 'x' + viewport.height;
      await observeCortex(viewport, 'cortex-' + size, pausedBaseline, viewport.width === 700 ? 'cortex-700x800' : null);
    }

    await step('close-cortex-by-real-button-at-700x800', async item => {
      const close = page.locator('#v70-tactics [data-v70-close]');
      await close.scrollIntoViewIfNeeded();
      await settle();
      const measured = await measure(true), continuity = await page.evaluate(pausedContinuity);
      item.observation = { close: measured.cortex.close, panel: measured.cortex.panel, continuity };
      assertCortex(measured);
      assert(contained(measured.cortex.close.rect, measured.viewport), 'The scrolled close button is outside the viewport.');
      assert.deepEqual(continuity, pausedBaseline, 'Scrolling the Cortex changed campaign resources.');
      // A normal Playwright click also verifies actionability; no forced click,
      // direct closeModals() call or synthetic activation is substituted here.
      await close.click();
      await resumed();
      // At this width the historical consumables gate still applies after the
      // menu closes. This isolated check does not qualify the narrow-screen HUD.
      const narrowConsumables = await page.locator('#quick28').evaluate(node => ({
        viewport: { width: innerWidth, height: innerHeight }, display: getComputedStyle(node).display,
        atMost760px: matchMedia('(max-width:760px)').matches,
        paused: !!paused, openModal: !!document.querySelector('.modal.open'),
        bodyMenuOpen: document.body.classList.contains('v34-menu-open'),
      }));
      item.observation.narrowConsumables = narrowConsumables;
      assert.deepEqual(narrowConsumables.viewport, { width: 700, height: 800 });
      assert.equal(narrowConsumables.atMost760px, true);
      assert.equal(narrowConsumables.paused || narrowConsumables.openModal || narrowConsumables.bodyMenuOpen, false);
      assert.equal(narrowConsumables.display, 'none', 'The historical #quick28 narrow-screen gate was lost after closing Cortex.');
      return { closeBeforeClick: measured.cortex.close, viewport: measured.viewport, returnedToExploration: true, narrowConsumables };
    });

    await observeHud(HUD_VIEWPORTS.at(-1), 'hud-after-cortex-return-1440x1000');

    let legacyBaseline;
    await step('open-cortex-through-existing-urban-menu', async item => {
      await page.keyboard.press('Tab');
      await page.locator('#cortex.open').waitFor({ state: 'visible' });
      await settle();
      const urban = await measure(true);
      item.observation = urban;
      assertMasked(urban);
      assert.equal(urban.paused, true);
      assert.deepEqual(urban.openModals, ['cortex']);
      legacyBaseline = await page.evaluate(pausedContinuity);
      const button = page.locator('#cortex [data-v70-open]');
      assert.equal(await button.count(), 1);
      assert.match(await button.textContent(), /Augmentations actives/);
      await button.scrollIntoViewIfNeeded();
      await button.click();
      await page.locator('#v70-tactics.open .panel').waitFor({ state: 'visible' });
      await settle();
      assert.deepEqual(await page.evaluate(pausedContinuity), legacyBaseline, 'The existing Cortex entry changed campaign resources.');
      return { entry: 'Tab → Cortex urbain → Augmentations actives', continuity: legacyBaseline, hudConcealedInUrbanMenu: true };
    });
    await observeCortex(HUD_VIEWPORTS.at(-1), 'cortex-return-1440x1000', legacyBaseline);
    await step('close-cortex-with-real-shortcut', async () => {
      await page.keyboard.press('Shift+F1');
      await resumed();
      const measured = await measure(false);
      assertHud(measured);
      return { shortcut: 'Shift+F1', returnedToExploration: true, viewport: measured.viewport };
    });

    await step('runtime-and-network-errors', async () => {
      await settle();
      assert.equal(report.eventOverflow, undefined, 'Error log overflowed; inspect the failing page.');
      assert.deepEqual(report.pageErrors, [], 'Unexpected page exceptions.');
      assert.deepEqual(report.consoleErrors, [], 'Unexpected browser console errors.');
      assert.deepEqual(report.httpErrors, [], 'Unexpected HTTP failures.');
      assert.deepEqual(report.requestFailures, [], 'Unexpected network request failures.');
      return { pageErrors: 0, consoleErrors: 0, httpErrors: 0, requestFailures: 0, warningsRecorded: report.consoleWarnings.length };
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
    // Deliberate browser teardown lies outside the observed page session.
    report.observationFinishedAt = new Date().toISOString();
    observing = false;
    currentStep = 'cleanup';
    try { await deadline(browser?.close(), 15000, 'Browser cleanup'); }
    catch (closeError) { report.closeError = errorRecord(closeError); }
    report.finishedAt = new Date().toISOString();
    const reportPath = path.join(output, 'report.json');
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8');
    process.stdout.write(JSON.stringify({ passed: report.passed, report: reportPath,
      steps: report.steps.map(({ name, status }) => ({ name, status })),
      ...(failure ? { error: failure.message } : {}) }, null, 2) + '\n');
  }
  if (failure) process.exitCode = 1;
}

main().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });
