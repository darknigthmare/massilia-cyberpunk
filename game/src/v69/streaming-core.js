/* Bounded metropolitan asset loading. A verified tile is not a certified 1:1 scene. */
(function (root) {
  'use strict';
  const SCHEMA = 'soma-metropole/world-manifest/1';
  const ORIGIN = [892951.6480966414, 6247274.566415883];
  const LAYERS = ['vector', 'terrain', 'surfaces', 'navigation'];
  const HASH = /^[a-f0-9]{64}$/i;
  const forbidden = new Set(['__proto__', 'prototype', 'constructor']);
  const fail = message => { throw new Error('Métropole : ' + message); };
  const plain = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const clone = value => JSON.parse(JSON.stringify(value));
  const finiteBounds = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite) && value[0] < value[2] && value[1] < value[3];

  function cellIdGrid(id) {
    if (typeof id !== 'string') return null;
    let match = id.match(/^V52-MC-([1-5])([1-5])$/);
    if (match) return {gridX:Number(match[2])-3, gridY:Number(match[1])-3};
    match = id.match(/^V52-MC-([EW])(\d{2,4})-([NS])(\d{2,4})$/);
    return match ? {gridX:(match[1] === 'W' ? -1 : 1)*Number(match[2]),
      gridY:(match[3] === 'N' ? -1 : 1)*Number(match[4])} : null;
  }

  function safePath(path) {
    return typeof path === 'string' && path.length <= 1000 && /^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(path) &&
      !path.includes('//') && !path.split('/').some(part => !part || part === '.' || part === '..');
  }

  function validateAsset(value, label) {
    if (!plain(value) || !safePath(value.path) || !HASH.test(value.sha256 || '') ||
        !Number.isSafeInteger(value.bytes) || value.bytes <= 0 || !['gzip-json','json'].includes(value.encoding)) {
      fail('description de fichier invalide : ' + label);
    }
    return {...clone(value), sha256:value.sha256.toLowerCase()};
  }

  function validateManifest(input) {
    if (!plain(input) || input.schema !== SCHEMA || input.crs !== 'EPSG:2154' || input.units !== 'm' ||
        input.cellSize !== 250 || !Array.isArray(input.origin) || input.origin.length !== 2 ||
        input.origin.some((n,i) => !Number.isFinite(n) || Math.abs(n-ORIGIN[i]) > 1e-6)) {
      fail('schéma, projection ou origine métrique incompatibles');
    }
    if (input.coverageExplicitPartial !== true) fail('la couverture partielle doit être déclarée');
    if (!plain(input.target) || input.target.id !== '200054807' ||
        input.target.boundarySHA256 !== null && !HASH.test(input.target.boundarySHA256 || '')) {
      fail('périmètre métropolitain invalide');
    }
    if (!plain(input.source) || !HASH.test(input.source.sha256 || '') ||
        !['license','attribution'].every(key => typeof input.source[key] === 'string' && input.source[key].trim() && input.source[key].length <= 4000)) {
      fail('provenance source incomplète');
    }
    if (!Array.isArray(input.tiles) || input.tiles.length > 100000) fail('liste de tuiles hors budget');
    const ids = new Set(), positions = new Set();
    const tiles = input.tiles.map(raw => {
      const grid = cellIdGrid(raw?.cellId);
      if (!plain(raw) || !grid || !Number.isInteger(raw.gridX) || !Number.isInteger(raw.gridY) ||
          raw.gridX !== grid.gridX || raw.gridY !== grid.gridY || !finiteBounds(raw.boundsL93)) fail('identifiant ou emprise de tuile invalide');
      const x = ORIGIN[0]+raw.gridX*250, n = ORIGIN[1]-raw.gridY*250;
      const expected = [x-125,n-125,x+125,n+125];
      if (expected.some((value,i) => Math.abs(raw.boundsL93[i]-value) > .001)) fail('tuile décalée du carroyage historique');
      const position = raw.gridX + ':' + raw.gridY;
      if (ids.has(raw.cellId) || positions.has(position)) fail('tuile ou position dupliquée');
      ids.add(raw.cellId); positions.add(position);
      const terrainOnly = raw.terrainOnly === true;
      if (terrainOnly && (raw.vector !== null || !raw.terrain || raw.surfaces != null ||
          raw.navigation != null || raw.contentSHA256 !== null)) {
        fail('tuile de terrain seul contradictoire ou incomplète');
      }
      const tile = {...clone(raw), vector:terrainOnly ? null : validateAsset(raw.vector, raw.cellId + '/vector')};
      for (const layer of LAYERS.slice(1)) tile[layer] = raw[layer] == null ? null : validateAsset(raw[layer], raw.cellId+'/'+layer);
      return tile;
    });
    // The tile definitions were already copied and validated above. Copying
    // the full input here would serialize tens of thousands of tiles again
    // before immediately discarding that duplicate array.
    const header = {...input};
    delete header.tiles;
    return {...clone(header), source:{...clone(input.source), sha256:input.source.sha256.toLowerCase()}, tiles};
  }

  function missingLayers(tile, loaded = null) {
    return LAYERS.filter(layer => !tile?.[layer] || loaded && !Object.hasOwn(loaded,layer));
  }

  function bytesOf(value) {
    if (value instanceof Uint8Array) return value;
    if (value instanceof ArrayBuffer) return new Uint8Array(value);
    if (ArrayBuffer.isView(value)) return new Uint8Array(value.buffer,value.byteOffset,value.byteLength);
    fail('réponse binaire attendue');
  }

  async function sha256(value) {
    const bytes = bytesOf(value);
    if (root.crypto?.subtle) {
      const digest = await root.crypto.subtle.digest('SHA-256', bytes);
      return [...new Uint8Array(digest)].map(n => n.toString(16).padStart(2,'0')).join('');
    }
    if (typeof require === 'function') return require('node:crypto').createHash('sha256').update(bytes).digest('hex');
    fail('SHA-256 indisponible');
  }

  async function boundedRead(stream, maximum, signal) {
    const reader = stream.getReader(), chunks = []; let size = 0;
    try {
      while (true) {
        if (signal?.aborted) throw abortError();
        const {value,done} = await reader.read(); if (done) break;
        const bytes = bytesOf(value); size += bytes.byteLength;
        if (size > maximum) fail('fichier dépassant le budget de lecture');
        chunks.push(bytes);
      }
    } catch (error) {
      try { await reader.cancel(error); } catch {}
      throw error;
    } finally { reader.releaseLock(); }
    const out = new Uint8Array(size); let at = 0;
    for (const chunk of chunks) {out.set(chunk,at); at += chunk.length;}
    return out;
  }

  async function defaultDecode(bytes, encoding, options) {
    if (encoding === 'json') return bytes;
    if (typeof DecompressionStream !== 'function') fail('décompression gzip indisponible');
    return boundedRead(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip')),
      options.maxDecodedBytes, options.signal);
  }

  function abortError() {
    const error = new Error('Chargement métropolitain annulé'); error.name = 'AbortError'; return error;
  }

  function parseJSON(bytes) {
    const text = new TextDecoder('utf-8', {fatal:true}).decode(bytes);
    return JSON.parse(text, (key,value) => {if (forbidden.has(key)) fail('clé JSON interdite'); return value;});
  }

  function validateVector(record, tile, manifest) {
    if (!plain(record) || record.schema !== 'soma-massilia/geodata-cell/4' || record.cellId !== tile.cellId ||
        !finiteBounds(record.boundsL93) || record.boundsL93.some((v,i) => Math.abs(v-tile.boundsL93[i]) > .001) ||
        String(record.sourceReceipt?.sha256 || '').toLowerCase() !== manifest.source.sha256 || record.v53Synthetic || record.v50Synthetic || record.testOnly ||
        record.featureCollection?.type !== 'FeatureCollection' || !Array.isArray(record.featureCollection.features)) {
      fail('tuile vectorielle contradictoire avec son manifeste');
    }
    return record;
  }

  function createTileStore(options) {
    const manifest = validateManifest(options?.manifest);
    const byId = new Map(manifest.tiles.map(tile => [tile.cellId,tile]));
    const maxResidentBytes = options.maxResidentBytes ?? 128*1024*1024;
    const maxCompressedBytes = options.maxCompressedBytes ?? 16*1024*1024;
    const maxDecodedBytes = options.maxDecodedBytes ?? 64*1024*1024;
    const memoryFactor = options.memoryFactor ?? 4;
    const maxInFlight = options.maxInFlight ?? 2;
    const maxPending = options.maxPending ?? 64;
    if (![maxResidentBytes,maxCompressedBytes,maxDecodedBytes].every(n => Number.isSafeInteger(n) && n > 0) ||
        !Number.isFinite(memoryFactor) || memoryFactor < 1 || memoryFactor > 16 ||
        !Number.isInteger(maxInFlight) || maxInFlight < 1 || maxInFlight > 2 ||
        !Number.isInteger(maxPending) || maxPending < 1 || maxPending > 256) fail('budgets de chargement invalides');
    for (const name of ['onAttach','onDetach']) {
      if (options[name] && (typeof options[name] !== 'function' || options[name].constructor?.name === 'AsyncFunction')) {
        fail(name + ' doit être une fonction synchrone');
      }
    }
    const resident = new Map(), pending = new Map(), queue = [], protectedIds = new Set();
    let accountedBytes = 0, running = 0, clock = 0, epoch = 0;
    const counts = {loads:0, cacheHits:0, evictions:0, cancelled:0, failures:0};
    const baseURL = options.baseURL || root.location?.href;
    const fetchBytes = options.fetchBytes || (async (path, settings) => {
      if (!baseURL) fail('URL du manifeste absente');
      const response = await fetch(new URL(path,baseURL), {signal:settings.signal,credentials:'same-origin'});
      if (!response.ok || !response.body) fail('lecture refusée : HTTP ' + response.status);
      return boundedRead(response.body,settings.maxBytes,settings.signal);
    });
    const decodeBytes = options.decodeBytes || defaultDecode;
    const validators = options.validators || {};
    const active = task => {if (task.cancelled || task.epoch !== epoch) throw abortError();};

    function detach(id) {
      const entry = resident.get(id); if (!entry) return false;
      if (protectedIds.has(id)) fail('éviction refusée : cellule protégée');
      const detached = options.onDetach?.(id,entry);
      if (detached && typeof detached.then === 'function') fail('onDetach doit être synchrone');
      resident.delete(id); accountedBytes -= entry.accountedBytes; counts.evictions++;
      return true;
    }

    function roomFor(required, replacing) {
      if (required > maxResidentBytes) fail('tuile dépassant le budget mémoire du cache');
      const candidates = [...resident.values()].filter(entry => entry.cellId !== replacing && !protectedIds.has(entry.cellId))
        .sort((a,b) => a.lastUsed-b.lastUsed || a.cellId.localeCompare(b.cellId));
      const current = accountedBytes-(resident.get(replacing)?.accountedBytes || 0);
      const available = candidates.reduce((sum,entry) => sum+entry.accountedBytes,0);
      if (current+required-available > maxResidentBytes) fail('cache rempli par les cellules protégées');
      let used = current;
      for (const entry of candidates) {if (used+required <= maxResidentBytes) break; used -= entry.accountedBytes; detach(entry.cellId);}
    }

    async function asset(task, layer) {
      const description = task.tile[layer];
      if (!description) fail('couche absente : ' + layer);
      if (description.bytes > maxCompressedBytes) fail('taille compressée hors budget');
      active(task);
      const raw = bytesOf(await fetchBytes(description.path,{signal:task.controller.signal,
        maxBytes:Math.min(description.bytes,maxCompressedBytes),layer,tile:task.tile}));
      active(task);
      if (raw.byteLength !== description.bytes || raw.byteLength > maxCompressedBytes) fail('taille du fichier incorrecte');
      if (await sha256(raw) !== description.sha256) fail('empreinte SHA-256 incorrecte');
      active(task);
      const decoded = bytesOf(await decodeBytes(raw,description.encoding,{maxDecodedBytes,signal:task.controller.signal}));
      active(task);
      if (decoded.byteLength > maxDecodedBytes) fail('taille décompressée hors budget');
      let value = parseJSON(decoded);
      if (layer === 'vector') value = validateVector(value,task.tile,manifest);
      if (validators[layer]) value = await validators[layer](value,task.tile,manifest);
      active(task);
      if (!value || typeof value !== 'object') fail('validateur de couche sans données');
      return {value,decodedBytes:decoded.byteLength};
    }

    async function run(task) {
      active(task);
      const previous = resident.get(task.id);
      const layers = {...previous?.layers}, sizes = {...previous?.sizes};
      // Additional callers may request dependencies while a vector is in flight.
      while (true) {
        const next = [...task.wanted].find(layer => !Object.hasOwn(layers,layer));
        if (!next) break;
        const loaded = await asset(task,next); layers[next] = loaded.value; sizes[next] = loaded.decodedBytes;
      }
      active(task);
      const decodedBytes = Object.values(sizes).reduce((sum,n) => sum+n,0);
      const entry = {cellId:task.id,tile:task.tile,layers,sizes,decodedBytes,
        accountedBytes:Math.ceil(decodedBytes*memoryFactor),lastUsed:++clock,
        missingLayers:missingLayers(task.tile,layers),readyFor3D:false};
      entry.readyFor3D = entry.missingLayers.length === 0 && options.canActivate?.(entry,manifest) === true;
      roomFor(entry.accountedBytes,task.id);
      active(task);
      // Registry attachment is synchronous, so changing targets cannot leave a
      // half-attached asynchronous scene after the generation was cancelled.
      const attached = options.onAttach?.(task.id,entry,previous || null);
      if (attached && typeof attached.then === 'function') fail('onAttach doit être synchrone');
      accountedBytes -= resident.get(task.id)?.accountedBytes || 0;
      resident.set(task.id,entry); accountedBytes += entry.accountedBytes; counts.loads++; task.done = true;
      return entry;
    }

    function pump() {
      while (running < maxInFlight && queue.length) {
        const task = queue.shift(); if (task.cancelled) continue;
        running++;
        run(task).then(task.resolve,error => {
          if (error.name !== 'AbortError') counts.failures++;
          task.reject(error);
        }).finally(() => {
          if (pending.get(task.id) === task) pending.delete(task.id);
          running--; pump();
        });
      }
    }

    function load(id, settings = {}) {
      const tile = byId.get(id);
      if (!tile) return Promise.reject(new Error('Métropole : tuile absente du manifeste'));
      const wanted = settings.require3D ? LAYERS.slice() : settings.layers || ['vector'];
      if (!Array.isArray(wanted) || !wanted.length || wanted.some(layer => !LAYERS.includes(layer) || !tile[layer])) {
        return Promise.reject(new Error('Métropole : couches requises absentes'));
      }
      const cached = resident.get(id);
      if (cached && wanted.every(layer => Object.hasOwn(cached.layers,layer))) {
        // Terrain/catalogue availability can change while the verified bytes
        // stay cached. Publish a fresh status wrapper, leaving entries already
        // returned to callers or captured by an in-flight upgrade untouched.
        try {
          const refreshed = {...cached,lastUsed:clock+1,
            missingLayers:missingLayers(tile,cached.layers),readyFor3D:false};
          refreshed.readyFor3D = refreshed.missingLayers.length === 0 && options.canActivate?.(refreshed,manifest) === true;
          resident.set(id,refreshed); clock++; counts.cacheHits++; return Promise.resolve(refreshed);
        } catch (error) {return Promise.reject(error);}
      }
      const existing = pending.get(id);
      if (existing && !existing.cancelled && !existing.done) {
        for (const layer of wanted) existing.wanted.add(layer);
        return existing.promise.then(entry => wanted.every(layer => Object.hasOwn(entry.layers,layer)) ? entry : load(id,settings));
      }
      if ([...pending.values()].filter(task=>!task.cancelled&&!task.done).length >= maxPending) {
        return Promise.reject(new Error('Métropole : file de chargement hors budget'));
      }
      const task = {id,tile,wanted:new Set(wanted),epoch,cancelled:false,controller:new AbortController()};
      task.promise = new Promise((resolve,reject) => {task.resolve = resolve; task.reject = reject;});
      pending.set(id,task); queue.push(task); pump(); return task.promise;
    }

    function cancelTask(task) {
      if (task.cancelled) return;
      task.cancelled = true; task.controller.abort(); counts.cancelled++;
      task.reject(abortError()); if (pending.get(task.id) === task) pending.delete(task.id);
    }

    function protect(ids) {
      const next = Array.from(ids || []);
      if (next.some(id => !byId.has(id))) fail('protection de tuile inconnue');
      protectedIds.clear(); for (const id of next) protectedIds.add(id);
    }

    function request(ids, settings = {}) {
      const wanted = [...new Set(ids || [])];
      if (wanted.some(id => !byId.has(id))) return Promise.reject(new Error('Métropole : cible inconnue'));
      if (wanted.length > maxPending) return Promise.reject(new Error('Métropole : nombre de cibles hors budget'));
      protect(settings.protectedIds || wanted);
      epoch++;
      for (const task of pending.values()) {
        if (wanted.includes(task.id)) task.epoch = epoch;
        else cancelTask(task);
      }
      return Promise.allSettled(wanted.map(id => load(id,{require3D:settings.require3D === true,layers:settings.layers})));
    }

    return {manifest,load,request,protect,
      cancel() {epoch++; for (const task of [...pending.values()]) cancelTask(task);},
      remove(id) {return detach(id);},
      get(id) {const entry=resident.get(id);if(entry)entry.lastUsed=++clock;return entry || null;},
      snapshot() {return {schema:'soma-metropole/streaming-status/1',epoch,resident:resident.size,
        residentIds:[...resident.keys()],accountedBytes,maxResidentBytes,memoryFactor,
        accounting:'decoded UTF-8 bytes multiplied by memoryFactor; not a browser heap measurement',
        running,queued:queue.filter(task=>!task.cancelled).length,maxPending,protectedIds:[...protectedIds],
        ...counts,readyFor3D:[...resident.values()].filter(entry=>entry.readyFor3D).map(entry=>entry.cellId)};}
    };
  }

  const API = {SCHEMA,ORIGIN:ORIGIN.slice(),LAYERS:LAYERS.slice(),validateManifest,cellIdGrid,
    missingLayers,sha256,createTileStore};
  root.__SOMA_STREAM69_CORE__ = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
