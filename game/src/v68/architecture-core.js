/* SOMA//MASSILIA 0.68 — Source-aware architecture, independent of the renderer.
 * Source coordinates and tags are never changed. Material colours and regional
 * defaults are artistic interpretations, not measurements of real façades.
 */
(function (root) {
  'use strict';

  const EPSILON = 1e-4; // 0.1 mm: joins prepared Lambert-93 wall fragments.
  const NAMED_COLOURS = {
    black: '#000000', white: '#ffffff', grey: '#808080', gray: '#808080',
    lightgrey: '#d3d3d3', lightgray: '#d3d3d3', darkgrey: '#a9a9a9',
    darkgray: '#a9a9a9', silver: '#c0c0c0', beige: '#f5f5dc',
    ivory: '#fffff0', cream: '#fffdd0', tan: '#d2b48c', brown: '#a52a2a',
    maroon: '#800000', red: '#ff0000', darkred: '#8b0000', orange: '#ffa500',
    yellow: '#ffff00', lightyellow: '#ffffe0', gold: '#ffd700',
    salmon: '#fa8072', pink: '#ffc0cb', green: '#008000', darkgreen: '#006400',
    olive: '#808000', blue: '#0000ff', lightblue: '#add8e6', navy: '#000080',
    teal: '#008080', turquoise: '#40e0d0', purple: '#800080', violet: '#ee82ee',
    terracotta: '#c76b4e', ochre: '#cc7722', sand: '#c2b280'
  };
  const MATERIAL_COLOURS = {
    plaster: '#d8c7aa', stone: '#c6bba5', limestone: '#d5cbb4',
    sandstone: '#c9ab86', brick: '#ad765b', concrete: '#aaa89c',
    cement_block: '#a9a69a', wood: '#9b8060', metal: '#89938f',
    steel: '#929b98', glass: '#7b9693', mirror: '#8da9a8',
    copper: '#7b9d87', roof_tiles: '#b66f51', tiles: '#b66f51',
    slate: '#6e777c', asphalt: '#62625c', tar_paper: '#62625c'
  };
  const REGIONAL_WALLS = ['#cbb99b', '#d5c8ad', '#c7b39a', '#d9cbae', '#c3b49b'];
  const REGIONAL_ROOFS = ['#a87558', '#b47b59', '#a96b50', '#b18363'];
  // Values above 1.25 are the renderer's explicit emissive marker, reserved
  // for this fictional lighting layer. Source surface colours remain <= 1.
  const LIGHT_COLOURS = {
    amber: [1.8, 0.78, 0.3],
    cyan: [0.06, 1.6, 1.9],
    magenta: [1.8, 0.12, 1.45]
  };
  const LIGHT_FAMILIES = ['cyan', 'magenta', 'amber'];
  const WINDOW_DARK = [0.035, 0.06, 0.085];

  function parseColour(value) {
    if (typeof value !== 'string') return null;
    let text = value.trim().toLowerCase();
    const name = text.replace(/[ _-]/g, '');
    if (Object.hasOwn(NAMED_COLOURS, name)) text = NAMED_COLOURS[name];
    if (/^#[0-9a-f]{3}$/.test(text)) {
      text = '#' + [...text.slice(1)].map(character => character + character).join('');
    }
    if (/^#[0-9a-f]{6}$/.test(text)) {
      return [1, 3, 5].map(offset => parseInt(text.slice(offset, offset + 2), 16) / 255);
    }
    const rgb = text.match(/^rgb\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)$/);
    if (rgb) {
      const channels = rgb.slice(1).map(Number);
      if (channels.every(channel => channel >= 0 && channel <= 255)) {
        return channels.map(channel => channel / 255);
      }
    }
    return null;
  }

  function hash(value) {
    let result = 2166136261;
    for (const character of String(value ?? '')) {
      result ^= character.charCodeAt(0);
      result = Math.imul(result, 16777619);
    }
    return result >>> 0;
  }

  function materialColour(value) {
    if (typeof value !== 'string') return null;
    const name = value.trim().toLowerCase();
    return Object.hasOwn(MATERIAL_COLOURS, name) ? parseColour(MATERIAL_COLOURS[name]) : null;
  }

  function accentFamily(sourceId) {
    return hash(String(sourceId ?? '') + ':accent') % LIGHT_FAMILIES.length;
  }

  function appearance(properties = {}, seed = '') {
    const p = properties || {};
    let wall = parseColour(p['building:colour']) || parseColour(p['building:color']);
    let wallSource = wall ? 'osm-building-colour' : null;
    if (!wall) {
      wall = materialColour(p['building:material']);
      if (wall) wallSource = 'osm-building-material';
    }
    if (!wall) {
      wall = parseColour(REGIONAL_WALLS[hash(seed) % REGIONAL_WALLS.length]);
      wallSource = 'interpreted-marseille-palette';
    }
    let roof = parseColour(p['roof:colour']) || parseColour(p['roof:color']);
    let roofSource = roof ? 'osm-roof-colour' : null;
    if (!roof) {
      roof = materialColour(p['roof:material']);
      if (roof) roofSource = 'osm-roof-material';
    }
    if (!roof) {
      roof = parseColour(REGIONAL_ROOFS[hash(String(seed) + ':roof') % REGIONAL_ROOFS.length]);
      roofSource = 'interpreted-marseille-palette';
    }
    const accentIndex = accentFamily(p.canonical_id || seed);
    return {
      wall, roof, trim: wall.map(channel => channel * 0.71), wallSource, roofSource,
      accent: LIGHT_COLOURS[LIGHT_FAMILIES[accentIndex]].slice(),
      secondaryAccent: LIGHT_COLOURS[LIGHT_FAMILIES[(accentIndex + 1) % LIGHT_FAMILIES.length]].slice(),
      windowDark: WINDOW_DARK.slice(), windowWarm: LIGHT_COLOURS.amber.slice(),
      lightingSource: 'interpreted-cyberpunk-lighting'
    };
  }

  function windowLight(sourceId, row, slot) {
    if (!Number.isSafeInteger(row) || row < 0 || !Number.isSafeInteger(slot)) {
      throw new TypeError('Window lights require a non-negative floor row and an integer global facade slot.');
    }
    // Only canonical source identity, floor row and GLOBAL cadence slot enter
    // the pattern. Cell boundaries, call order and time cannot make it flicker.
    const identity = String(sourceId ?? '');
    const token = identity + ':row:' + row + ':slot:' + slot;
    const lit = hash(token + ':on') / 0x100000000 < 0.55;
    if (!lit) return {lit: false, colour: WINDOW_DARK.slice(), accentFamily: 'off'};
    // Most occupied windows retain warm domestic light; the building's stable
    // cyan/magenta/amber family supplies the remaining cyberpunk accents.
    const family = hash(token + ':colour') % 100 < 65 ? 'amber' : LIGHT_FAMILIES[accentFamily(identity)];
    return {lit: true, colour: LIGHT_COLOURS[family].slice(), accentFamily: family};
  }

  function finitePoint(point) {
    return Array.isArray(point) && point.length >= 2 &&
      Number.isFinite(point[0]) && Number.isFinite(point[1]);
  }

  function pointKey(point) {
    return Math.round(point[0] / EPSILON) + ',' + Math.round(point[1] / EPSILON);
  }

  function referenceKey(properties = {}, sourceId = '', record = {}) {
    const p = properties || {};
    return JSON.stringify([
      record?.sourceReceipt?.sha256 || '',
      String(p.canonical_id || sourceId || ''),
      String(p['soma:geometry_sha256'] || '')
    ]);
  }

  function inRing(point, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const a = ring[i], b = ring[j];
      if ((a[1] > point[1]) !== (b[1] > point[1]) &&
          point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) {
        inside = !inside;
      }
    }
    return inside;
  }

  // Closed SOURCE wall chains prove that the canonical boundary is present.
  // Cut-cell edges occur only in ringsL93 and cannot close an incomplete source.
  function closeSourceRings(walls) {
    const points = new Map(), adjacency = new Map();
    for (const [a, b] of walls) {
      const ka = pointKey(a), kb = pointKey(b);
      if (ka === kb) continue;
      points.set(ka, a); points.set(kb, b);
      if (!adjacency.has(ka)) adjacency.set(ka, new Set());
      if (!adjacency.has(kb)) adjacency.set(kb, new Set());
      adjacency.get(ka).add(kb); adjacency.get(kb).add(ka);
    }
    if (adjacency.size < 3 || [...adjacency.values()].some(neighbours => neighbours.size !== 2)) {
      return {complete: false, rings: []};
    }
    const visited = new Set(), rings = [];
    for (const start of [...adjacency.keys()].sort()) {
      if (visited.has(start)) continue;
      const ring = [];
      let previous = null, current = start;
      do {
        if (visited.has(current)) return {complete: false, rings: []};
        visited.add(current); ring.push(points.get(current).slice());
        const next = [...adjacency.get(current)].sort().find(key => key !== previous);
        previous = current; current = next;
      } while (current !== start);
      if (ring.length < 3) return {complete: false, rings: []};
      rings.push(ring);
    }
    return {complete: true, rings};
  }

  function referenceIndex(records) {
    const index = new Map();
    const values = records instanceof Map ? records.values() : records || [];
    for (let record of values) {
      if (Array.isArray(record) && record.length === 2) record = record[1];
      if (!record || record.v53Synthetic || record.v50Synthetic || record.testOnly) continue;
      for (const feature of record.featureCollection?.features || []) {
        const p = feature?.properties || {};
        if (p['soma:layer'] !== 'buildings' && p.logical_layer !== 'buildings') continue;
        const sourceId = String(p.canonical_id || feature.id || '');
        if (!sourceId || !p['soma:geometry_sha256']) continue;
        const key = referenceKey(p, sourceId, record);
        if (!index.has(key)) index.set(key, {key, sourceId, pointMap: new Map(), wallMap: new Map()});
        const reference = index.get(key);
        for (const mesh of p['soma:mesh53'] || []) {
          for (const ring of mesh.ringsL93 || []) {
            for (const point of ring) {
              if (finitePoint(point)) reference.pointMap.set(pointKey(point), point.slice(0, 2));
            }
          }
          for (const wall of mesh.wallsL93 || []) {
            if (!Array.isArray(wall) || wall.length !== 2 || !wall.every(finitePoint)) continue;
            const a = wall[0].slice(0, 2), b = wall[1].slice(0, 2);
            const ka = pointKey(a), kb = pointKey(b);
            if (ka === kb) continue;
            reference.wallMap.set([ka, kb].sort().join('|'), ka < kb ? [a, b] : [b, a]);
          }
        }
      }
    }
    for (const [key, reference] of index) {
      const points = [...reference.pointMap.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, point]) => point);
      const walls = [...reference.wallMap.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, wall]) => wall);
      const bounds = points.reduce((b, p) => [Math.min(b[0], p[0]), Math.min(b[1], p[1]), Math.max(b[2], p[0]), Math.max(b[3], p[1])], [Infinity, Infinity, -Infinity, -Infinity]);
      const closed = closeSourceRings(walls);
      let outerCount = 0, hasHoles = false;
      for (const ring of closed.rings) {
        const depth = closed.rings.filter(other => other !== ring && inRing(ring[0], other)).length;
        if (depth % 2 === 0) outerCount++;
        else hasHoles = true;
      }
      const validBounds = bounds.every(Number.isFinite) && bounds[2] - bounds[0] > EPSILON && bounds[3] - bounds[1] > EPSILON;
      index.set(key, {
        key, sourceId: reference.sourceId, points, walls, rings: closed.rings,
        bounds: validBounds ? bounds : null,
        complete: closed.complete && validBounds,
        outerCount, hasHoles,
        simple: closed.complete && outerCount === 1 && !hasHoles && closed.rings[0]?.length === 4,
        frame: validBounds ? {origin: bounds.slice(0, 2), width: bounds[2] - bounds[0], height: bounds[3] - bounds[1]} : null
      });
    }
    return index;
  }

  function measure(value) {
    if (typeof value === 'number') return Number.isFinite(value) && value >= 0 ? value : null;
    if (typeof value !== 'string') return null;
    const text = value.trim().replace(',', '.');
    const feet = text.match(/^(\d+(?:\.\d+)?)\s*'\s*(\d+(?:\.\d+)?)\s*(?:"|in)?$/);
    if (feet) return Number(feet[1]) * 0.3048 + Number(feet[2]) * 0.0254;
    const match = text.match(/^(\d+(?:\.\d+)?)\s*(m|metres?|meters?|cm|ft|feet|'|in|inches?|\")?$/i);
    if (!match) return null;
    const unit = (match[2] || 'm').toLowerCase();
    const factor = unit === 'cm' ? 0.01 : /^(ft|feet|')$/.test(unit) ? 0.3048 : /^(in|inch|inches|\")$/.test(unit) ? 0.0254 : 1;
    return Number(match[1]) * factor;
  }

  function direction(value) {
    if (typeof value !== 'number' && typeof value !== 'string') return null;
    const text = String(value).trim();
    if (!/^(\d+(?:\.\d+)?)\s*°?$/.test(text)) return null;
    const degrees = Number(text.replace('°', '').trim());
    return degrees >= 0 && degrees <= 360 ? (degrees % 360) * Math.PI / 180 : null;
  }

  function roofPlan(properties = {}, dimensions = {}, reference = null) {
    const p = properties || {}, dim = dimensions || {};
    const requestedShape = String(p['roof:shape'] || '').trim().toLowerCase();
    const validHeight = Number.isFinite(dim.height) && dim.height > 0 && dim.height <= 1000;
    const total = validHeight ? dim.height : 0;
    const floor = dim.minHeight ?? 0;
    const fallback = reason => ({shape: 'flat', requestedShape, modelled: false, reason,
      eave: total, heightAt: () => total, breakLines: []});
    if (!validHeight || !Number.isFinite(floor) || floor < 0 || total <= floor + 0.05 || dim.valid === false) {
      return fallback('invalid-dimensions');
    }
    if (requestedShape === 'flat') {
      return {shape: 'flat', requestedShape, modelled: true, reason: 'osm-flat',
        eave: total, heightAt: () => total, breakLines: []};
    }
    if (requestedShape !== 'skillion') {
      return fallback(requestedShape ? 'unsupported-roof-shape' : 'roof-shape-unavailable');
    }
    const explicitHeight = measure(p.height), roofHeight = measure(p['roof:height']);
    if (explicitHeight === null || Math.abs(explicitHeight - total) > 1e-5) {
      return fallback('explicit-total-height-required');
    }
    if (roofHeight === null || roofHeight <= 0 || roofHeight > total - floor + 1e-5) {
      return fallback('invalid-or-missing-roof-height');
    }
    const angle = direction(p['roof:direction']);
    if (angle === null) return fallback('roof-direction-required');
    if (!reference?.complete || !reference.bounds || reference.outerCount !== 1) {
      return fallback('incomplete-canonical-reference');
    }
    const origin = reference.bounds.slice(0, 2), de = Math.sin(angle), dn = Math.cos(angle);
    const projected = reference.points.map(point => (point[0] - origin[0]) * de + (point[1] - origin[1]) * dn);
    const minimum = Math.min(...projected), maximum = Math.max(...projected), span = maximum - minimum;
    if (!Number.isFinite(span) || span <= EPSILON) return fallback('degenerate-roof-reference');
    // A roof-only building:part may start exactly at min_height. Several
    // surveyed Marseille skillion parts use this valid, zero-wall-height case.
    const eave = Math.max(floor, total - roofHeight);
    const rise = total - eave;
    return {
      shape: 'skillion', requestedShape, modelled: true, reason: 'osm-skillion', eave,
      // OSM roof:direction points DOWN the slope; height includes the roof.
      heightAt(easting, northing) {
        const t = ((easting - origin[0]) * de + (northing - origin[1]) * dn - minimum) / span;
        return eave + rise * (1 - Math.max(0, Math.min(1, t)));
      },
      breakLines: []
    };
  }

  function roofTriangles(triangles, plan, projector) {
    if (!Array.isArray(triangles) || typeof plan?.heightAt !== 'function' || typeof projector?.toMetric !== 'function') {
      throw new TypeError('Roof triangulation requires triangles, a roof plan and a metric projector.');
    }
    // Flat and skillion roofs are planes: retain the prepared triangulation,
    // including courtyard holes and source clipping, without adding any area.
    return triangles.map(triangle => {
      if (!Array.isArray(triangle) || triangle.length !== 3 || !triangle.every(finitePoint)) {
        throw new TypeError('Invalid prepared roof triangle.');
      }
      return triangle.map(point => {
        const metric = projector.toMetric(point);
        if (!finitePoint(metric)) throw new TypeError('Invalid metric roof coordinate.');
        const height = plan.heightAt(metric[0], metric[1]);
        if (!Number.isFinite(height)) throw new TypeError('Invalid roof height.');
        return [point[0], height, point[1]];
      });
    });
  }

  function facadePanels(aLocal, bLocal, projector, sourceId, width = 1.1, spacing = 3.6, offset = 0) {
    if (!finitePoint(aLocal) || !finitePoint(bLocal) || typeof projector?.toMetric !== 'function' ||
        !Number.isFinite(width) || width <= 0 || !Number.isFinite(spacing) || spacing <= 0 ||
        !Number.isFinite(offset)) {
      throw new TypeError('Facade panels require metric endpoints, positive width/spacing and a finite offset.');
    }
    const a = projector.toMetric(aLocal.slice(0, 2));
    const b = projector.toMetric(bLocal.slice(0, 2));
    if (!finitePoint(a) || !finitePoint(b)) throw new TypeError('Invalid metric facade coordinate.');
    const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (length <= 1e-9) return [];

    // A canonical tangent makes a reversed source wall use the same slots.
    // Quantisation affects the cadence frame only, never source coordinates:
    // prepared intersections can differ by floating-point noise across cells.
    let de = (b[0] - a[0]) / length, dn = (b[1] - a[1]) / length;
    if (Math.abs(de) < 1e-8) { de = 0; dn = dn < 0 ? -1 : 1; }
    if (Math.abs(dn) < 1e-8) { dn = 0; de = de < 0 ? -1 : 1; }
    if (de < 0 || (de === 0 && dn < 0)) { de = -de; dn = -dn; }
    const angle = Math.round(Math.atan2(dn, de) / 1e-8) * 1e-8;
    de = Math.cos(angle); dn = Math.sin(angle);

    // Fixed Lambert-93 cadence origin near Marseille avoids cancellation from
    // the 6.2-million-metre northings. It does not move the rendered endpoints.
    const along = point => (point[0] - 900000) * de + (point[1] - 6250000) * dn;
    const sa = along(a), sb = along(b), low = Math.min(sa, sb), high = Math.max(sa, sb);
    const start = sa <= sb ? aLocal : bLocal, end = sa <= sb ? bLocal : aLocal;
    const span = high - low;
    if (span <= 1e-9) return [];
    const phase = hash(sourceId) / 0x100000000 * spacing + offset;
    const first = Math.ceil((low - width / 2 - phase) / spacing);
    const last = Math.floor((high + width / 2 - phase) / spacing);
    if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last) || last - first > 100000) {
      throw new RangeError('Facade cadence exceeds the geometry budget.');
    }
    const result = [];
    for (let slot = first; slot <= last; slot++) {
      const center = phase + slot * spacing;
      const left = Math.max(low, center - width / 2);
      const right = Math.min(high, center + width / 2);
      if (right - left <= 1e-9) continue;
      const t = ((left + right) / 2 - low) / span;
      result.push({
        center: [start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t],
        width: right - left,
        slot
      });
    }
    return result;
  }

  const API = {VERSION: '0.68.0', parseColour, appearance, windowLight, referenceKey, referenceIndex, roofPlan, roofTriangles, facadePanels};
  root.__SOMA_ARCH68_CORE__ = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : globalThis);
