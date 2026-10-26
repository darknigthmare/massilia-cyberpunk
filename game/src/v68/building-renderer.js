/* Architecture overlay. Source footprints, terrain datums and collision volumes stay shared. */
(function (root) {
  'use strict';
  const K = root.__SOMA_ARCH68_CORE__;
  let sourceRecords = null;
  let references = new Map();

  function reference(p, sourceId, record) {
    if (String(p['roof:shape'] || '').toLowerCase() !== 'skillion') return null;
    const records = root.__SOMA_V52__?.records();
    // records() returns a fresh Map view; compare immutable record objects,
    // otherwise the full city would be indexed again for every building.
    const unchanged = records && sourceRecords && records.size === sourceRecords.size &&
      [...records].every(([id, value]) => sourceRecords.get(id) === value);
    if (records && !unchanged) {
      const needed = [...records.values()].map(value => ({...value,
        featureCollection: {...value.featureCollection,
          features: (value.featureCollection?.features || []).filter(feature =>
            String(feature.properties?.['roof:shape'] || '').toLowerCase() === 'skillion')}}));
      references = K.referenceIndex(needed);
      sourceRecords = records;
    }
    return references.get(K.referenceKey(p, sourceId, record));
  }

  function beginCell(z) {
    z.v68Architecture = {buildings: 0, sourceWalls: 0, sourceRoofs: 0, slopingRoofs: 0,
      unresolvedRoofs: 0, litWindows: 0, neonPanels: 0};
  }

  function normal(a, b, c) {
    const u = b.map((v, i) => v - a[i]), v = c.map((n, i) => n - a[i]);
    const n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]];
    const length = Math.hypot(...n) || 1;
    return n.map(x => x / length);
  }

  function panel(g, center, tangent, outward, width, height, color) {
    const [x, y, z] = center, [tx, tz] = tangent;
    const points = [[x-tx*width/2,y-height/2,z-tz*width/2],
      [x+tx*width/2,y-height/2,z+tz*width/2],
      [x+tx*width/2,y+height/2,z+tz*width/2],
      [x-tx*width/2,y+height/2,z-tz*width/2]];
    const n = normal(...points.slice(0, 3));
    if (n.reduce((sum, v, i) => sum + v * outward[i], 0) < 0) points.reverse();
    g.quad(...points, outward, color);
  }

  function render(z, g, rings, p, sourceId, index, partIndex, helpers) {
    const {geometryMesh53, addPolygonCollider, C50, C, inPolygon, dimension, heightReference} = helpers;
    const mesh = geometryMesh53(z, rings, p, partIndex);
    if (!mesh || mesh.area < .1) return false;
    const dim = dimension(p, C50.buildingHeight(p, sourceId), heightReference(p, sourceId, z));
    if (!dim.valid) { z.v59InvalidDimensions = (z.v59InvalidDimensions || 0) + 1; return false; }
    const seed = C50.stableHash(sourceId), material = K.appearance(p, seed);
    const plan = K.roofPlan(p, dim, reference(p, sourceId, z.v50Record));
    const h = dim.height, floor = dim.minHeight, canopy = dim.openStructure;
    const cellStats = z.v68Architecture || (beginCell(z), z.v68Architecture);
    const metric = q => z.v50Projector.toMetric(q);
    const roofY = q => plan.heightAt(...metric(q));

    if (z.v50Record?.v53Validated && !z.v50Record.v53Synthetic) {
      const collider = addPolygonCollider(z, mesh.rings, 'building');
      if (collider && floor > 0) {
        const base = g.__v56?.kind === 'rigid' ? g.__v56.height : 0;
        collider.v60Volume = {bottom: base+floor, top: base+h, sourceId,
          minHeight: floor, height: h, heightSource: dim.heightSource,
          kind: canopy ? 'canopy' : 'elevated-building', groundAltitude: base};
      }
    } else if (floor < 1.8) addPolygonCollider(z, mesh.rings, 'building');

    // Lift only existing triangles: interior courtyards and clipped edges are never filled.
    for (const triangle of K.roofTriangles(mesh.triangles, plan, z.v50Projector)) {
      let [a, b, c] = triangle, n = normal(a, b, c);
      if (n[1] < 0) { [b, c] = [c, b]; n = normal(a, b, c); }
      g.tri(a, b, c, n, material.roof);
    }

    for (let i = 0; i < mesh.walls.length && !canopy; i++) {
      const [a, b] = mesh.walls[i], dx = b[0]-a[0], dz = b[1]-a[1], len = Math.hypot(dx, dz);
      if (len < .01) continue;
      const tx = dx/len, tz = dz/len;
      let outward = [tz, 0, -tx];
      const midpoint = [(a[0]+b[0])/2, (a[1]+b[1])/2];
      if (inPolygon([midpoint[0]+outward[0]*.02, midpoint[1]+outward[2]*.02], mesh.rings)) {
        outward = outward.map(v => -v);
      }
      const topA = roofY(a), topB = roofY(b);
      const face = [[a[0],floor,a[1]], [b[0],floor,b[1]], [b[0],topB,b[1]], [a[0],topA,a[1]]];
      if ((-dz)*outward[0]+dx*outward[2] < 0) face.reverse();
      // Shade by orientation, not fragment-local wall order: no colour seams.
      g.quad(...face, outward, C.mul(material.wall, .92+.06*Math.abs(outward[0])));

      // Window/shutter layouts are a visual interpretation, not surveyed facade detail.
      const clearHeight = Math.min(topA, topB)-floor;
      if (clearHeight > 5) {
        const rows = Math.min(6, Math.floor((clearHeight-1)/3.05));
        const patterns = [
          {type:'glass',width:1.1,offset:0,height:1.15,dy:0},
          {type:'shutter',width:.308,offset:-.726,height:1.18,dy:0},
          {type:'shutter',width:.308,offset:.726,height:1.18,dy:0},
          {type:'sill',width:1.232,offset:0,height:.1,dy:-.64}
        ].map(pattern => ({...pattern, panels:K.facadePanels(a,b,z.v50Projector,sourceId,pattern.width,3.6,pattern.offset)}));
        for (let row = 0; row < rows; row++) {
          const y = floor+1.85+row*3.05;
          if (y+.65 >= Math.min(topA, topB)) continue;
          for (const pattern of patterns) for (const item of pattern.panels) {
            const x = item.center[0]+outward[0]*.035, zz = item.center[1]+outward[2]*.035;
            const tone = ((seed+row+item.slot)%4+4)%4;
            let color;
            if (pattern.type === 'glass') {
              const light = K.windowLight(sourceId,row,item.slot);
              color = light.colour;
              if (light.lit) cellStats.litWindows++;
            } else if (pattern.type === 'sill') {
              // Reuse existing facade panels for interpreted neon details;
              // no signs, obstacles or unsourced buildings enter the map.
              const neon = row===0 && ((seed+item.slot)%3+3)%3===0;
              color = neon ? material.accent : C.mul(material.wall,.72);
              if (neon) cellStats.neonPanels++;
            } else {
              color = C.mul(C.mix(material.trim,[.08,.16,.21],.42),.78+tone*.06);
            }
            panel(g,[x,y+pattern.dy,zz],[tx,tz],outward,item.width,pattern.height,color);
          }
        }
      }
    }

    z.v50Footprints.push({sourceId, ring: mesh.rings[0], holes: mesh.rings.slice(1),
      height: h, minHeight: floor, openStructure: canopy, area: mesh.area,
      heightSource: dim.heightSource, ignReference: dim.ignId, groundAltitude: dim.groundAltitude,
      roofShape: dim.roofShape, geometrySource: z.v50Record.v53Validated ? 'declared-source' : 'legacy',
      v68: {roofModelled: plan.modelled, roofShape: plan.shape, roofReason: plan.reason,
        wallSource: material.wallSource, roofSource: material.roofSource,
        lightingSource: material.lightingSource}});
    const stats = z.v68Architecture || (beginCell(z), z.v68Architecture);
    stats.buildings++;
    if (material.wallSource.startsWith('osm-')) stats.sourceWalls++;
    if (material.roofSource.startsWith('osm-')) stats.sourceRoofs++;
    if (plan.modelled && plan.shape !== 'flat') stats.slopingRoofs++;
    if (plan.requestedShape && !plan.modelled) stats.unresolvedRoofs++;
    return true;
  }

  root.__SOMA_ARCH68__ = {render, beginCell, invalidate() {sourceRecords = null;},
    referenceCount: () => references.size};
})(typeof window !== 'undefined' ? window : globalThis);
