/* Unsupported vertical access is withheld, never flattened into a DTM road.
 * Geometry, source-node identity, road direction and navigation stay unchanged.
 */
(function (root) {
  'use strict';
  const wrapped = new WeakSet();
  let ready = false;
  function positive(value) {
    return !['', 'no', 'false', '0'].includes(String(value ?? '').trim().toLowerCase());
  }
  function reasons(properties = {}) {
    const p = properties || {}, output = [];
    const layer = Number(p.layer || 0);
    if (!Number.isFinite(layer) || layer !== 0) output.push('nonzero-or-unknown-layer');
    for (const field of ['bridge', 'tunnel', 'covered', 'indoor']) {
      if (positive(p[field])) output.push(field);
    }
    return output;
  }
  function unsupported(properties) { return reasons(properties).length !== 0; }
  function profile(properties, original) {
    const withheld = reasons(properties);
    return withheld.length ? {...original, structural:true, v69Withheld:true, v69WithheldReasons:withheld} : original;
  }
  function install() {
    const dimensions = root.__SOMA_FIDELITY59_CORE__;
    const terrain = root.__SOMA_TERRAIN56_CORE__;
    if (dimensions && !wrapped.has(dimensions)) {
      const original = dimensions.roadProfile;
      dimensions.roadProfile = p => profile(p, original(p));
      wrapped.add(dimensions);
    }
    if (terrain && !wrapped.has(terrain)) {
      const original = terrain.structure;
      terrain.structure = p => unsupported(p) || original(p);
      wrapped.add(terrain);
    }
    ready = !!dimensions && !!terrain;
    if (!ready && typeof document !== 'undefined') setTimeout(install, 80);
    return ready;
  }
  const api = {version:'0.69.0', reasons, unsupported, profile, install,
    get ready() { return ready; },
    stairs:'No surveyed step elevations: mapped axes and IGN terrain are preserved; no invented step volumes.'};
  root.__SOMA_ROADS69__ = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined') install();
})(typeof window !== 'undefined' ? window : globalThis);
