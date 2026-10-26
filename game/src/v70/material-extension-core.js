/* Explicit OSM appearance tags, layered over the unchanged architecture core.
 * Material names select interpreted opaque colours, never surveyed textures,
 * transparency, façade layouts or fictional signs. Source records stay intact.
 */
(function (root) {
  'use strict';
  const K = root.__SOMA_ARCH68_CORE__ ||
    (typeof require === 'function' ? require('../v68/architecture-core.js') : null);
  if (!K) throw new Error('Architecture core must load before material extension 0.70.');
  const baseAppearance = K.appearance, baseParseColour = K.parseColour;
  const MATERIAL_PALETTE = Object.freeze({
    plastic: '#c7cec8', grass: '#688458', gravel: '#929189',
    acrylic_glass: '#a9c9cb', fabric: '#c8bc9e'
  });
  const normalized = value => typeof value === 'string' ? value.trim().toLowerCase() : '';

  function parseColour(value) {
    // Aqua is a standard CSS colour name (#00ffff), not a neon/emission flag.
    return normalized(value) === 'aqua' ? [0, 1, 1] : baseParseColour(value);
  }

  function declaredColour(p, keys) {
    for (const key of keys) {
      const colour = parseColour(p[key]);
      if (colour) return {colour, key};
    }
    return null;
  }

  function evidence(p, key, kind) {
    return {
      tag: key, value: key === null ? null : p[key],
      interpretation: kind,
      colourAccuracy: kind === 'declared-colour' ? 'source-declared-not-certified' : 'interpreted',
      colourMeasurementVerified: false,
      ...(kind === 'material-palette' ? {
        materialIsColourMeasurement: false, surfaceModel: 'opaque-colour-only',
        textureSurveyed: false
      } : {})
    };
  }

  function appearance(properties = {}, seed = '') {
    const p = properties || {}, result = baseAppearance(p, seed);
    const wallColour = declaredColour(p, ['building:colour', 'building:color']);
    const roofColour = declaredColour(p, ['roof:colour', 'roof:color']);
    if (wallColour) {
      result.wall = wallColour.colour;
      result.wallSource = 'osm-building-colour';
      result.wallColourEvidence = evidence(p, wallColour.key, 'declared-colour');
    } else if (normalized(p['building:facade:material']) === 'glass') {
      // The façade-specific declaration wins over a generic building material.
      result.wall = baseAppearance({'building:material': 'glass'}, seed).wall;
      result.wallSource = 'osm-building-facade-material';
      result.wallColourEvidence = evidence(p, 'building:facade:material', 'material-palette');
    } else if (normalized(p['building:material']) === 'plastic') {
      result.wall = baseParseColour(MATERIAL_PALETTE.plastic);
      result.wallSource = 'osm-building-material';
      result.wallColourEvidence = evidence(p, 'building:material', 'material-palette');
    } else {
      result.wallColourEvidence = result.wallSource === 'osm-building-material' ?
        evidence(p, 'building:material', 'material-palette') : evidence(p, null, 'regional-palette');
    }
    if (roofColour) {
      result.roof = roofColour.colour;
      result.roofSource = 'osm-roof-colour';
      result.roofColourEvidence = evidence(p, roofColour.key, 'declared-colour');
    } else if (Object.hasOwn(MATERIAL_PALETTE, normalized(p['roof:material']))) {
      result.roof = baseParseColour(MATERIAL_PALETTE[normalized(p['roof:material'])]);
      result.roofSource = 'osm-roof-material';
      result.roofColourEvidence = evidence(p, 'roof:material', 'material-palette');
    } else {
      result.roofColourEvidence = result.roofSource === 'osm-roof-material' ?
        evidence(p, 'roof:material', 'material-palette') : evidence(p, null, 'regional-palette');
    }
    result.trim = result.wall.map(channel => channel * .71);
    return result;
  }

  const API = Object.freeze({VERSION: '0.70.0', appearance, parseColour});
  root.__SOMA_MATERIAL70_CORE__ = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : globalThis);
