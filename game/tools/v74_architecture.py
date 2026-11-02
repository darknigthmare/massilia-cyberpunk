"""Reviewed source-bound shared roof foundations over the rebuilt v73 parent."""
import re

MODULES = ('architecture-datum-core',)


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Ancre architecture74 absente ou dupliquée : ' + old[:90])
    return text.replace(old, new, 1)


def rewrite(html, identifier, transform):
    pattern = r'(<script id="' + re.escape(identifier) + r'">)([\s\S]*?)(</script>)'
    matches = list(re.finditer(pattern, html))
    if len(matches) != 1:
        raise ValueError('Script architecture74 absent ou dupliqué : ' + identifier)
    match = matches[0]
    result = transform(match[2])
    if '</script' in result.lower():
        raise ValueError('Fermeture de script architecture74 interdite.')
    return html[:match.start(2)] + result + html[match.end(2):]


def inject(html, scripts, anchor, identifier):
    source = scripts.get(MODULES[0])
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module architecture74 absent ou invalide.')
    if '__SOMA_ARCHITECTURE74__' in html:
        raise ValueError('Architecture74 déjà injectée.')
    return once(html, anchor, '<script id="' + identifier + '">\n' + source + '\n</script>\n' + anchor)


def patch_html(html, scripts):
    # The reviewed AMP identity is absent from the frozen campaign snapshot.
    # Expose the edition's read-only report without changing campaign geometry.
    return inject(html, scripts, '<script id="soma-roof-fidelity73-core">', 'soma-architecture74-core')


def patch_viewer(html, scripts):
    html = inject(html, scripts, '<script id="viewer-metropole-viewer">', 'viewer-architecture74-core')
    html = rewrite(html, 'viewer-metropole-viewer', lambda text: once(text,
        'return {canonicalDatumsMap:datums,missingCanonicalDatums,omitBuildingIds,references:architecture.referenceIndex(useful),maxVertices:600000,maxWindowRows:3};',
        'return root.__SOMA_ARCHITECTURE74__.reconcile(selected,architecture,parts,{canonicalDatumsMap:datums,missingCanonicalDatums,omitBuildingIds,references:architecture.referenceIndex(useful),maxVertices:600000,maxWindowRows:3});'))
    html = rewrite(html, 'viewer-metropole-viewer-core', lambda text: once(text,
        'facts:root.__SOMA_ARCHITECTURE71_CORE__.facts(p,dim,plan,material,record,base)',
        'facts:root.__SOMA_ARCHITECTURE74__.facts(root.__SOMA_ARCHITECTURE71_CORE__.facts(p,dim,plan,material,record,base),options.architectureDatum74?.get(id))'))
    return rewrite(html, 'viewer-architecture71-runtime', lambda text: once(text,
        "        row('Toiture',s.roof.displayedShape",
        "        if(s.datum74)row('Fondation commune interprétée',s.datum74.supportId+' · '+s.datum74.parentId,'Association géométrique dérivée des contours source ; tolérance de quantification OSM de 1 cm, sans précision de relevé certifiée. Hauteurs OSM relatives à cette fondation ; aucun lien de relation OSM déclaré.');\n        row('Toiture',s.roof.displayedShape"))


def audit_native_catalogue(vector_manifest, world_manifest, report):
    """Optional GIS audit, outside the normal stdlib-only reconstruction path."""
    import hashlib
    import json
    from pathlib import Path
    import sqlite3
    from shapely import from_wkb
    from shapely.geometry import mapping

    def digest_file(path):
        value = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                value.update(block)
        return value.hexdigest()

    vector_manifest, world_manifest, report = map(Path, (vector_manifest, world_manifest, report))
    manifest = json.loads(vector_manifest.read_text())
    world = json.loads(world_manifest.read_text())
    store = manifest['canonicalStore']
    catalogue = vector_manifest.parent / store['path']
    if catalogue.stat().st_size != store['bytes'] or digest_file(catalogue) != store['sha256']:
        raise ValueError('Native catalogue SHA256/size mismatch.')
    if digest_file(vector_manifest) != world['sourcePackSHA256'] or manifest['source']['sha256'] != world['source']['sha256']:
        raise ValueError('The native catalogue and installed world use different snapshots.')
    parent_id, support_id = 'osm/way/264740428', 'osm/way/264740436'
    roofs = ['osm/way/264740443', 'osm/way/264740444']
    db = sqlite3.connect(catalogue.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        def native(identity):
            raw = db.execute('SELECT properties,geometry FROM features WHERE id=?', (identity,)).fetchone()
            properties, geometry = json.loads(raw[0]), from_wkb(raw[1])
            geometry_sha = hashlib.sha256(json.dumps(mapping(geometry), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            if geometry_sha != properties['soma:geometry_sha256']:
                raise ValueError('Native geometry SHA256 mismatch: ' + identity)
            return properties, geometry

        parent_properties, parent = native(parent_id)
        support_properties, support = native(support_id)
        rows = []
        for identity in roofs:
            properties, roof = native(identity)
            w, s, e, n = roof.bounds
            candidates = []
            for candidate_id, encoded, encoded_geometry in db.execute(
                    "SELECT f.id,f.properties,f.geometry FROM features f JOIN feature_index i ON f.rowid=i.rowid "
                    "WHERE f.layer='buildings' AND i.minx<=? AND i.maxx>=? AND i.miny<=? AND i.maxy>=?", (e, w, n, s)):
                candidate = json.loads(encoded)
                if (not candidate.get('building') or candidate['building'] == 'roof' or
                        str(candidate.get('building:part', '')).lower() not in ('', 'no', 'false', '0')):
                    continue
                outline = from_wkb(encoded_geometry)
                # Shapely's finite circular arcs are inscribed in the exact
                # capsules used by JS. This independent check is conservative.
                if outline.buffer(.01, quad_segs=32).covers(roof):
                    candidates.append(candidate_id)
            if sorted(candidates) != [parent_id] or not parent.covers(support):
                raise ValueError('Non-unique native outline or unsupported source body.')
            if (float(properties['height']) != 23 or float(properties['min_height']) != 20 or
                    float(properties['roof:height']) != 3 or float(support_properties['height']) != 20):
                raise ValueError('Source vertical semantics changed.')
            relations = [row[0] for row in db.execute('SELECT id FROM source_relations WHERE members LIKE ?', ('%' + identity.rsplit('/', 1)[1] + '%',))]
            rows.append({'id': identity, 'geometrySHA256': properties['soma:geometry_sha256'],
                'parentId': parent_id, 'supportId': support_id, 'uniqueNativeOutline': candidates,
                'exactContainment': parent.covers(roof), 'outsideOutlineAreaM2': roof.difference(parent).area,
                'entireFootprintWithinBoundaryToleranceMeters': .01,
                'sourceBodyOverlapFraction': roof.intersection(support).area / roof.area,
                'nativeRelationsMentioningRoof': relations, 'association': 'derived-source-boundary-containment',
                'osmRelationAsserted': False, 'sourceHeightMeters': 23, 'sourceMinimumHeightMeters': 20,
                'sourceRoofRiseMeters': 3, 'sourceBodyHeightMeters': 20,
                'interpretation': 'Source total/minimum heights relative to an interpreted shared foundation; not surveyed.'})
    finally:
        db.close()
    result = {'schema': 'soma-massilia/architecture74-native-source-audit/1', 'passed': True,
        'sourcePbfSHA256': manifest['source']['sha256'], 'vectorManifestSHA256': digest_file(vector_manifest),
        'worldManifestSHA256': digest_file(world_manifest), 'canonicalStoreSHA256': store['sha256'],
        'canonicalStoreBytes': store['bytes'], 'parentGeometrySHA256': parent_properties['soma:geometry_sha256'],
        'supportGeometrySHA256': support_properties['soma:geometry_sha256'], 'boundaryToleranceMeters': .01,
        'toleranceMeaning': 'OSM coordinate quantisation bound, not survey accuracy',
        'sourceGeometryModified': False, 'associations': rows}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vector-manifest', required=True)
    parser.add_argument('--world-manifest', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit_native_catalogue(args.vector_manifest, args.world_manifest, args.report)
    print('Native source audit passed: ' + str(len(result['associations'])) + ' reviewed roof associations.')
