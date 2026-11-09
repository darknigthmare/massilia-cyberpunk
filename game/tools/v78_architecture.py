"""Source-clipped, bounded convex frames for explicit pyramidal OSM roofs."""
from pathlib import Path
import re
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_v68 import replace_once, rewrite_script

MODULES = ('architecture-roof-core',)


def once(text, old, new, label):
    return replace_once(text, old, new, 'architecture78: ' + label)


def patch_html(html, scripts):
    # The source cohort belongs to the independent metropolitan edition.
    return html


def patch_viewer(html, scripts):
    source = scripts.get(MODULES[0])
    if not isinstance(source, str) or not source.strip() or '</script' in source.lower():
        raise ValueError('Module architecture78 absent ou invalide.')
    if 'id="viewer-architecture78-core"' in html:
        raise ValueError('Architecture78 déjà appliquée.')
    pattern = r'<script id="viewer-roof-fidelity73-core">[\s\S]*?</script>'
    matches = list(re.finditer(pattern, html))
    if len(matches) != 1:
        raise ValueError('Toiture73 absente ou ambiguë.')
    end = matches[0].end()
    html = html[:end] + '\n<script id="viewer-architecture78-core">\n' + source + '\n</script>' + html[end:]
    html = rewrite_script(html, 'viewer-metropole-viewer-core', lambda body: once(body,
        'facts:root.__SOMA_ARCHITECTURE74__.facts(root.__SOMA_ARCHITECTURE71_CORE__.facts(p,dim,plan,material,record,base),options.architectureDatum74?.get(id))',
        'facts:root.__SOMA_ARCHITECTURE78_CORE__.facts(root.__SOMA_ARCHITECTURE74__.facts(root.__SOMA_ARCHITECTURE71_CORE__.facts(p,dim,plan,material,record,base),options.architectureDatum74?.get(id)),plan)',
        'distinguer cadre et contours source'))
    return rewrite_script(html, 'viewer-architecture71-runtime', lambda body: once(body,
        "        row('Toiture',s.roof.displayedShape",
        "        if(s.roofFrame78)row('Cadre de toiture interprété','Enveloppe convexe dérivée · borne de retrait 1 cm','Les deux contours complets sont comparés ; cette borne n’est pas une précision de relevé. Emprise, retraits et positions des murs source conservés ; nouveaux triangles de toiture limités aux triangles préparés. Le profil pyramidal et son sommet sont interprétés depuis la forme, la hauteur totale et la hauteur du toit déclarées OSM ; aucun faîtage relevé n’est ajouté.');\n        row('Toiture',s.roof.displayedShape",
        'rendre le profil et le sommet interprétés explicites'))


def audit_native(vector_manifest, native_geometry_report, fixture_path, report_path):
    """Optional independent GEOS audit; never imported by the stdlib build path."""
    import hashlib
    import json
    import sqlite3
    from shapely import from_wkb
    from shapely.affinity import translate
    from shapely.geometry import LineString, Point, Polygon, mapping
    from shapely.ops import unary_union

    def sha_file(path):
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()

    def metres(value):
        text = str(value).strip()
        if text.endswith(' m'):
            text = text[:-2]
        return float(text)

    vector_manifest, fixture_path, native_geometry_report, report_path = map(
        Path, (vector_manifest, fixture_path, native_geometry_report, report_path))
    manifest = json.loads(vector_manifest.read_bytes())
    fixture = json.loads(fixture_path.read_bytes())
    native = json.loads(native_geometry_report.read_bytes())
    store = manifest['canonicalStore']
    catalogue = vector_manifest.parent / store['path']
    if (sha_file(vector_manifest) != fixture['vectorManifestSHA256'] or
            manifest['source']['sha256'] != fixture['sourcePbfSHA256'] or
            catalogue.stat().st_size != store['bytes'] or sha_file(catalogue) != store['sha256'] or
            not native['passed'] or native['worldManifestSHA256'] != fixture['worldManifestSHA256']):
        raise ValueError('Independent audit source binding mismatch.')
    by_id = {row['id']: row for row in native['cohort']}
    if set(by_id) != {row['id'] for row in fixture['rows']} or len(by_id) != 6:
        raise ValueError('The source cohort changed.')
    rows = []
    db = sqlite3.connect(catalogue.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        for saved in fixture['rows']:
            row = by_id[saved['id']]
            properties, raw = db.execute('SELECT properties,geometry FROM features WHERE id=?', (saved['id'],)).fetchone()
            properties, polygon = json.loads(properties), from_wkb(raw)
            geometry_sha = hashlib.sha256(json.dumps(mapping(polygon), sort_keys=True,
                separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            if properties != saved['p'] or geometry_sha != properties['soma:geometry_sha256'] or geometry_sha != row['geometrySHA256']:
                raise ValueError('Canonical source attributes or geometry changed: ' + saved['id'])
            if polygon.geom_type == 'MultiPolygon' and len(polygon.geoms) == 1:
                polygon = polygon.geoms[0]
            if polygon.geom_type != 'Polygon' or not polygon.is_valid or polygon.interiors:
                raise ValueError('Unexpected source polygon.')
            # GEOS buffer/noding at sub-millimetre radii must use a local frame,
            # not coordinates around 6 million metres with large cancellation.
            origin = polygon.bounds[:2]
            local = lambda p: (p[0] - origin[0], p[1] - origin[1])
            polygon = translate(polygon, -origin[0], -origin[1])
            hull = polygon.convex_hull
            # GEOS circular buffer arcs are inscribed. Complete containment in
            # these smaller buffers is a conservative independent proof of the
            # entire boundary bound, not sampled-point Hausdorff evidence.
            bound = .01 - 1e-9
            near_source = hull.boundary.difference(polygon.boundary.buffer(bound, quad_segs=32)).is_empty
            near_frame = polygon.boundary.difference(hull.boundary.buffer(bound, quad_segs=32)).is_empty
            if not near_source or not near_frame or 1 - polygon.area / hull.area > .01:
                raise ValueError('The complete boundary exceeds the 1 cm guard.')
            if (row['totalHeightMeters'] != metres(properties['height']) or
                    row['eaveHeightMeters'] != metres(properties['height']) - metres(properties['roof:height']) or
                    row['minHeightMeters'] != metres(properties.get('min_height', 0)) or
                    not polygon.contains(Point(local(row['apexL93'])))):
                raise ValueError('Native vertical semantics or inferred apex mismatch.')
            source_union = unary_union([Polygon([local(p) for p in t]) for t in row['sourceTriangles']])
            roof_polygons = [Polygon([local(p) for p in t]) for t in row['roofTriangles']]
            roof_union = unary_union(roof_polygons)
            source_difference = source_union.symmetric_difference(polygon).area
            roof_difference = roof_union.symmetric_difference(source_union).area
            projected_sum = sum(p.area for p in roof_polygons)
            overlap = projected_sum - roof_union.area
            numerical_area_tolerance = max(1e-6, polygon.area * 1e-8)
            if max(source_difference, roof_difference, abs(overlap)) > numerical_area_tolerance:
                raise ValueError('Prepared source or roof coverage changed outside numerical clipping tolerance.')
            source_wall_union = unary_union([LineString([local(w['a']), local(w['b'])]) for w in row['walls']])
            if (not source_wall_union.difference(polygon.boundary.buffer(1e-7, quad_segs=32)).is_empty or
                    not polygon.boundary.difference(source_wall_union.buffer(1e-7, quad_segs=32)).is_empty):
                raise ValueError('Source wall positions or coverage changed.')
            rows.append({'id': saved['id'], 'geometrySHA256': geometry_sha,
                'entireBoundaryCapsulesBothDirections': True, 'guardMeters': .01,
                'sourceAreaM2': polygon.area, 'frameAreaM2': hull.area,
                'sourceTriangleDifferenceM2': source_difference, 'roofProjectedDifferenceM2': roof_difference,
                'roofProjectedOverlapM2': overlap, 'numericalAreaToleranceM2': numerical_area_tolerance,
                'sourceWallsPreservedWithinNumericalMeters': 1e-7,
                'baseAltitudeNGF': row['baseAltitudeNGF'], 'totalHeightMeters': row['totalHeightMeters'],
                'eaveHeightMeters': row['eaveHeightMeters'], 'minHeightMeters': row['minHeightMeters'],
                'maximumSourceWallAboveFrameEaveMeters': row['maximumSourceWallAboveFrameEaveMeters'],
                'openStructure': row['openStructure'], 'profileAndApexInferred': True})
    finally:
        db.close()
    result = {'schema': 'soma/architecture78-independent-source-audit/1', 'passed': True,
        'vectorManifestSHA256': fixture['vectorManifestSHA256'], 'canonicalStoreSHA256': store['sha256'],
        'canonicalStoreBytes': store['bytes'], 'sourcePbfSHA256': fixture['sourcePbfSHA256'],
        'nativeGeometryReportSHA256': sha_file(native_geometry_report), 'fixtureSHA256': sha_file(fixture_path),
        'method': 'Independent canonical WKB + GEOS complete boundary buffers and polygon unions; no sampled admission test.',
        'geometryScope': 'Independent viewer only', 'newModelledRoofs': len(rows), 'rows': rows,
        'limits': ['The frame 1 cm bound is not vertical precision or survey accuracy.',
                   'Pyramid facets and centered apex are interpreted from source tags, not surveyed roof geometry.']}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vector-manifest', required=True)
    parser.add_argument('--native-geometry-report', required=True)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit_native(args.vector_manifest, args.native_geometry_report, args.fixture, args.report)
    print('Independent source geometry audit passed: ' + str(result['newModelledRoofs']) + ' roofs.')
