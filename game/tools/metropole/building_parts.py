#!/usr/bin/env python3
"""Derive audited outline/part replacements without altering source records.

Geometry generation uses the optional GIS venv. ``loadproof`` deliberately uses
only the standard library, so the normal offline game build needs no GIS stack.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

SCHEMA = 'soma-massilia/building-parts-proof/1'
MIN_COVERAGE = 0.995
FALSE = {'', 'no', 'false', '0'}
ROOT = Path(__file__).resolve().parents[3]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def measure(value):
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) and value >= 0 else None
    if not isinstance(value, str):
        return None
    text = value.strip().replace(',', '.')
    feet = re.fullmatch(r'''(\d+(?:\.\d+)?)\s*'\s*(\d+(?:\.\d+)?)\s*(?:"|in)?''', text)
    if feet:
        return float(feet[1]) * .3048 + float(feet[2]) * .0254
    match = re.fullmatch(r'''(\d+(?:\.\d+)?)\s*(m|metres?|meters?|cm|ft|feet|'|in|inches?|\")?''', text, re.I)
    if not match:
        return None
    unit = (match[2] or 'm').lower()
    factor = .01 if unit == 'cm' else .3048 if unit in {'ft', 'feet', "'"} else .0254 if unit in {'in', 'inch', 'inches', '"'} else 1
    result = float(match[1]) * factor
    return result if math.isfinite(result) else None


def _collect(records, source_sha=None):
    """Collect immutable source bindings without importing a geometry library."""
    groups = {}
    hashes = set()
    values = records.values() if isinstance(records, dict) else records
    for record in values:
        if record.get('v53Synthetic') or record.get('v50Synthetic') or record.get('testOnly'):
            continue
        receipt = record.get('sourceReceipt', {}).get('sha256')
        if not isinstance(receipt, str) or not re.fullmatch('[0-9a-f]{64}', receipt):
            raise ValueError('A source PBF SHA256 is required on every real record.')
        hashes.add(receipt)
        cell = record.get('cellId')
        for feature in record.get('featureCollection', {}).get('features', []):
            p = feature.get('properties', {})
            if p.get('soma:layer') != 'buildings':
                continue
            identity = p.get('canonical_id') or feature.get('id')
            geometry_sha = p.get('soma:geometry_sha256')
            if not isinstance(identity, str) or not re.fullmatch(r'osm/(way|relation)/[1-9]\d*', identity):
                raise ValueError('A canonical OSM building identity is required.')
            if not isinstance(geometry_sha, str) or not re.fullmatch('[0-9a-f]{64}', geometry_sha):
                raise ValueError(f'Geometry SHA256 missing for {identity}.')
            row = groups.setdefault(identity, {'id': identity, 'properties': p,
                'geometrySHA256': geometry_sha, 'sourceSHA256': receipt, 'fragments': []})
            if row['geometrySHA256'] != geometry_sha or row['sourceSHA256'] != receipt:
                raise ValueError(f'Conflicting canonical source fragments for {identity}.')
            for part_index, mesh in enumerate(p.get('soma:mesh53', [])):
                row['fragments'].append({'cellId': cell, 'contentSHA256': record.get('contentSHA256'),
                    'boundsL93': record.get('boundsL93'), 'sourcePartIndex': part_index, 'mesh': mesh})
    if len(hashes) != 1:
        raise ValueError('Exactly one source PBF snapshot is required.')
    observed = hashes.pop()
    if source_sha is not None and source_sha != observed:
        raise ValueError('Source PBF SHA256 does not match the requested snapshot.')
    return groups, observed


def _closed_boundary(fragments):
    nodes = defaultdict(set)
    edges = set()
    for fragment in fragments:
        for a, b in fragment['mesh'].get('wallsL93', []):
            ka = tuple(round(float(v) * 10000) for v in a[:2])
            kb = tuple(round(float(v) * 10000) for v in b[:2])
            if ka == kb:
                continue
            edge = tuple(sorted((ka, kb)))
            if edge in edges:
                continue
            edges.add(edge)
            nodes[ka].add(kb)
            nodes[kb].add(ka)
    return len(nodes) >= 3 and all(len(neighbours) == 2 for neighbours in nodes.values())


def _relation_links(relations):
    links = defaultdict(set)
    evidence = defaultdict(set)
    types = {'w': 'way', 'way': 'way', 'r': 'relation', 'relation': 'relation'}
    for relation in relations or []:
        if relation.get('tags', {}).get('type') != 'building':
            continue
        members = relation.get('members', [])
        outlines = [f"osm/{types[m['type']]}/{int(m['ref'])}" for m in members
                    if m.get('role') == 'outline' and m.get('type') in types]
        parts = [f"osm/{types[m['type']]}/{int(m['ref'])}" for m in members
                 if m.get('role') == 'part' and m.get('type') in types]
        if len(outlines) != 1:
            continue
        for part in parts:
            links[part].add(outlines[0])
            evidence[(part, outlines[0])].add(f"osm/relation/{int(relation['id'])}")
    return links, evidence


def _polygons(geometry):
    if geometry.geom_type == 'Polygon':
        yield geometry
    elif hasattr(geometry, 'geoms'):
        for item in geometry.geoms:
            yield from _polygons(item)


def _no_exposed_cell_cuts(geometry, fragments):
    """Clipping can only introduce edges on a cell's rectangle boundary.

    A globally joined outline without exposed cell-cut edges is complete even
    when the separately prepared wall list omits an original wall segment.
    This proof never supplies or repairs missing wall geometry.
    """
    bounds = [fragment.get('boundsL93') for fragment in fragments]
    if not bounds or any(not isinstance(b, list) or len(b) != 4 for b in bounds):
        return False
    tolerance = .0001
    for polygon in _polygons(geometry):
        for ring in [polygon.exterior, *polygon.interiors]:
            points = list(ring.coords)
            for a, b in zip(points, points[1:]):
                for west, south, east, north in bounds:
                    vertical = any(abs(a[0]-x) <= tolerance and abs(b[0]-x) <= tolerance
                        and min(max(a[1], b[1]), north)-max(min(a[1], b[1]), south) > tolerance
                        for x in [west, east])
                    horizontal = any(abs(a[1]-y) <= tolerance and abs(b[1]-y) <= tolerance
                        and min(max(a[0], b[0]), east)-max(min(a[0], b[0]), west) > tolerance
                        for y in [south, north])
                    if vertical or horizontal:
                        return False
    return True


def _geometry_rows(groups):
    from shapely.geometry import Polygon, LineString
    from shapely.ops import unary_union
    result, withheld = {}, []
    for identity, row in groups.items():
        walls_closed = _closed_boundary(row['fragments'])
        polygons, walls = [], []
        valid = True
        for fragment in row['fragments']:
            mesh = fragment['mesh']
            rings = mesh.get('ringsL93', [])
            if not rings:
                valid = False
                break
            polygon = Polygon(rings[0], rings[1:])
            if not polygon.is_valid or polygon.is_empty:
                valid = False
                break
            polygons.append(polygon)
            walls.extend(LineString(wall) for wall in mesh.get('wallsL93', []))
        if not valid or not polygons:
            withheld.append({'id': identity, 'reason': 'invalid-source-polygon'})
            continue
        geometry = unary_union(polygons)
        if not geometry.is_valid or geometry.area <= .01:
            withheld.append({'id': identity, 'reason': 'invalid-source-union'})
            continue
        no_cuts = walls_closed or _no_exposed_cell_cuts(geometry, row['fragments'])
        if not no_cuts:
            withheld.append({'id': identity, 'reason': 'incomplete-source-wall-boundary'})
            continue
        result[identity] = {**row, 'geometry': geometry, 'boundary': unary_union(walls),
            'sourceWallsComplete': walls_closed,
            'footprintCompletenessProof': 'closed-source-wall-graph' if walls_closed else 'no-exposed-cell-cuts'}
    return result, withheld


def _ground_dimensions(properties):
    p = properties
    if str(p.get('building', '')).lower() == 'roof' or str(p.get('building:part', '')).lower() == 'roof':
        return None
    minimum = measure(p.get('min_height'))
    if minimum is None:
        levels = measure(p.get('building:min_level', 0))
        if levels is None:
            return None
        minimum = levels * 3.05
    height = measure(p.get('height'))
    if minimum != 0 or height is None or not (.05 < height <= 1000):
        return None
    return {'height': height, 'minHeight': 0, 'heightSource': 'osm-height'}


def _residual_by_cell(parent, residual):
    # Deferred: importing a saved proof during a normal build needs no GIS deps.
    try:
        from .import_tiles import mesh_for_polygon
    except ImportError:
        from import_tiles import mesh_for_polygon
    from shapely.geometry import Polygon
    result = {}
    for fragment in parent['fragments']:
        mesh = fragment['mesh']
        rings = mesh['ringsL93']
        source_polygon = Polygon(rings[0], rings[1:])
        cut = residual.intersection(source_polygon)
        record = result.setdefault(fragment['cellId'], {
            'contentSHA256': fragment['contentSHA256'], 'meshes': []})
        for polygon in _polygons(cut):
            if polygon.area <= 1e-8:
                continue
            derived = mesh_for_polygon(polygon, parent['boundary'])
            derived['sourcePartIndex'] = fragment['sourcePartIndex']
            record['meshes'].append(derived)
    return result


def generate_parts(records, *, source_sha=None, relations=None, relations_source_sha=None, min_coverage=MIN_COVERAGE):
    """Produce full/partial replacement evidence from complete source geometry.

    Ground parts require explicit OSM height and a zero base. A relation link
    must be bound to the same PBF, otherwise only unique strict geometric
    containment can establish association. Remaining outline geometry is kept.
    """
    if not MIN_COVERAGE <= min_coverage <= 1:
        raise ValueError('Full-outline suppression requires at least 99.5% ground coverage.')
    groups, source_sha = _collect(records, source_sha)
    if relations_source_sha is not None and relations_source_sha != source_sha:
        raise ValueError('Building relations come from a different PBF snapshot.')
    rows, withheld = _geometry_rows(groups)
    parents = {identity: row for identity, row in rows.items()
        if row['properties'].get('building') and str(row['properties'].get('building')).lower() != 'roof'
        and str(row['properties'].get('building:part', '')).lower() in FALSE}
    parts = {identity: row for identity, row in rows.items()
        if str(row['properties'].get('building:part', '')).lower() not in FALSE}
    from shapely.strtree import STRtree
    from shapely.ops import unary_union
    parent_ids = sorted(parents)
    tree = STRtree([parents[identity]['geometry'] for identity in parent_ids])
    links, relation_evidence = _relation_links(relations if relations_source_sha == source_sha else [])
    associations, ambiguity = defaultdict(list), []
    methods = {}
    for identity, part in sorted(parts.items()):
        explicit = sorted(parent for parent in links.get(identity, []) if parent in parents)
        if len(explicit) == 1:
            parent_id, method = explicit[0], 'osm-building-relation'
        elif len(explicit) > 1:
            ambiguity.append({'id': identity, 'reason': 'multiple-building-relation-parents', 'parents': explicit})
            continue
        else:
            contained = [parent_ids[int(index)] for index in tree.query(part['geometry'], predicate='covered_by')
                         if parent_ids[int(index)] != identity]
            if len(contained) != 1:
                if contained:
                    ambiguity.append({'id': identity, 'reason': 'ambiguous-geometric-parent', 'parents': sorted(contained)})
                continue
            parent_id, method = contained[0], 'unique-source-containment'
        associations[parent_id].append(identity)
        methods[(identity, parent_id)] = method
    report = {'schema': SCHEMA, 'sourceSHA256': source_sha, 'certified': False,
        'fullSuppressionThreshold': min_coverage, 'parents': {}, 'partParents': {},
        'ambiguities': ambiguity, 'withheldGeometry': withheld,
        'relationsEvidenceSHA256': digest(relations or []),
        'relationsSourceSHA256': relations_source_sha}
    for parent_id, associated in sorted(associations.items()):
        parent = parents[parent_id]
        ground = [identity for identity in associated if _ground_dimensions(parts[identity]['properties'])]
        if not ground:
            report['ambiguities'].append({'id': parent_id, 'reason': 'no-ground-parts-with-explicit-height', 'parts': associated})
            continue
        covering = unary_union([parts[identity]['geometry'] for identity in ground])
        covered = parent['geometry'].intersection(covering)
        residual = parent['geometry'].difference(covering)
        area = parent['geometry'].area
        ratio = covered.area / area
        conservation = abs(area-covered.area-residual.area)
        if conservation > max(.001, area*1e-8):
            raise ValueError(f'Area conservation failed for {parent_id}.')
        declared_height = measure(parent['properties'].get('height'))
        max_part_height = max((measure(parts[identity]['properties'].get('height')) or 0) for identity in associated)
        vertical_consistent = declared_height is None or max_part_height >= declared_height-.05
        if ratio >= min_coverage and not vertical_consistent:
            report['ambiguities'].append({'id': parent_id, 'reason': 'height-envelope-conflict',
                'coverageRatio': ratio, 'parentDeclaredHeight': declared_height,
                'maxDeclaredPartHeight': max_part_height, 'replacementRefused': True})
            continue
        # 99.5% is a minimum admission threshold, not permission to drop the
        # remaining source footprint: retain every non-numerical residual.
        full = ratio >= min_coverage and residual.area <= max(1e-7, area*1e-10)
        residual_cells = _residual_by_cell(parent, residual)
        residual_mesh_area = sum(mesh['areaM2'] for cell in residual_cells.values() for mesh in cell['meshes'])
        if abs(residual_mesh_area-residual.area) > max(.001, area*1e-7):
            raise ValueError(f'Residual mesh area failed for {parent_id}.')
        entry = {'parentId': parent_id, 'parentGeometrySHA256': parent['geometrySHA256'],
            'sourceSHA256': source_sha, 'name': parent['properties'].get('name'),
            'status': 'derived-complete' if full else 'derived-partial',
            'replaceParent': True, 'suppressParent': full, 'remainingUnresolved': not full,
            'association': sorted({methods[(identity, parent_id)] for identity in associated}),
            'parentAreaM2': area, 'coveredAreaM2': covered.area, 'coverageRatio': ratio,
            'uncoveredAreaM2': residual.area, 'residualAreaM2': residual.area,
            'residualMeshAreaM2': residual_mesh_area, 'areaConservationErrorM2': conservation,
            'partIds': sorted(associated), 'groundPartIds': sorted(ground), 'parts': [],
            'residualByCell': residual_cells,
            'cells': {fragment['cellId']: fragment['contentSHA256'] for fragment in parent['fragments']},
            'datumSource': 'shared-parent-source-terrain-anchor',
            'accuracy': 'derived-geometry-not-certified', 'artificialCutWalls': False,
            'scope': 'source-records-listed-in-cells'}
        entry['sourceFootprintComplete'] = True
        entry['sourceWallsComplete'] = parent['sourceWallsComplete']
        entry['footprintCompletenessProof'] = parent['footprintCompletenessProof']
        entry['parentDeclaredHeight'] = declared_height
        entry['maxDeclaredPartHeight'] = max_part_height
        entry['verticalEnvelopeConsistent'] = vertical_consistent
        for identity in sorted(associated):
            part = parts[identity]
            binding = {'id': identity, 'geometrySHA256': part['geometrySHA256'],
                'height': measure(part['properties'].get('height')),
                'groundCoverage': identity in ground, 'association': methods[(identity, parent_id)],
                'cells': {fragment['cellId']: fragment['contentSHA256'] for fragment in part['fragments']}}
            binding['buildingRelations'] = sorted(relation_evidence.get((identity, parent_id), []))
            entry['parts'].append(binding)
            report['partParents'][identity] = {'parentId': parent_id,
                'parentGeometrySHA256': parent['geometrySHA256'], 'geometrySHA256': part['geometrySHA256'],
                'sourceSHA256': source_sha, 'association': methods[(identity, parent_id)],
                'cells': binding['cells']}
        report['parents'][parent_id] = entry
        if not full:
            report['ambiguities'].append({'id': parent_id, 'reason': 'incomplete-ground-part-coverage',
                'coverageRatio': ratio, 'unresolvedAreaM2': residual.area, 'fullSuppressionRefused': True})
    report['statistics'] = {'sourceBuildings': len(groups), 'completeGeometry': len(rows),
        'fullParents': sum(row['suppressParent'] for row in report['parents'].values()),
        'partialParents': sum(not row['suppressParent'] for row in report['parents'].values()),
        'associatedParts': len(report['partParents']),
        'groundParts': sum(len(row['groundPartIds']) for row in report['parents'].values())}
    report['proofSHA256'] = digest(report)
    return report


def loadproof(path_or_dict, records=None, source_sha=None):
    """Validate a saved proof using stdlib; optionally bind it to raw records."""
    proof = json.loads(Path(path_or_dict).read_text(encoding='utf-8')) if isinstance(path_or_dict, (str, Path)) else copy.deepcopy(path_or_dict)
    if not isinstance(proof, dict) or proof.get('schema') != SCHEMA:
        raise ValueError('Unsupported building-parts proof schema.')
    stored = proof.get('proofSHA256')
    content = {key: value for key, value in proof.items() if key != 'proofSHA256'}
    if stored != digest(content):
        raise ValueError('Building-parts proof checksum mismatch.')
    if not MIN_COVERAGE <= proof.get('fullSuppressionThreshold', 0) <= 1:
        raise ValueError('Building-parts proof weakens the suppression threshold.')
    if source_sha is not None and source_sha != proof.get('sourceSHA256'):
        raise ValueError('Building-parts proof uses a different source snapshot.')
    metadata = None
    if records is not None:
        metadata, observed = _collect(records, proof.get('sourceSHA256'))
    for parent_id, parent in proof.get('parents', {}).items():
        for key in ['parentAreaM2', 'coveredAreaM2', 'residualAreaM2', 'coverageRatio', 'areaConservationErrorM2']:
            value = parent.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'Invalid area evidence for {parent_id}.')
        if parent.get('sourceSHA256') != proof.get('sourceSHA256'):
            raise ValueError('Parent source binding mismatch.')
        if parent.get('suppressParent') and parent['coverageRatio'] < proof['fullSuppressionThreshold']:
            raise ValueError('Insufficient coverage to suppress a source outline.')
        if parent.get('suppressParent') and (parent['residualAreaM2'] > max(1e-7, parent['parentAreaM2']*1e-10)
                or not parent.get('verticalEnvelopeConsistent')):
            raise ValueError('A full replacement would lose unresolved source geometry or height.')
        if parent.get('artificialCutWalls') is not False:
            raise ValueError('Artificial cut walls are not allowed.')
        if metadata is not None:
            source = metadata.get(parent_id)
            if not source or source['geometrySHA256'] != parent.get('parentGeometrySHA256'):
                raise ValueError(f'Stale parent geometry for {parent_id}.')
            bindings = {fragment['cellId']: fragment['contentSHA256'] for fragment in source['fragments']}
            if any(bindings.get(cell) != sha for cell, sha in parent.get('cells', {}).items()):
                raise ValueError(f'Stale parent record for {parent_id}.')
            for part in parent.get('parts', []):
                source_part = metadata.get(part['id'])
                if not source_part or source_part['geometrySHA256'] != part.get('geometrySHA256'):
                    raise ValueError(f'Stale building-part geometry for {part["id"]}.')
                part_bindings = {fragment['cellId']: fragment['contentSHA256'] for fragment in source_part['fragments']}
                if any(part_bindings.get(cell) != sha for cell, sha in part.get('cells', {}).items()):
                    raise ValueError(f'Stale building-part record for {part["id"]}.')
    for part_id, binding in proof.get('partParents', {}).items():
        parent = proof.get('parents', {}).get(binding.get('parentId'))
        parts = {part['id']: part for part in parent.get('parts', [])} if parent else {}
        part = parts.get(part_id)
        if (not parent or not part or binding.get('sourceSHA256') != proof.get('sourceSHA256')
                or binding.get('parentGeometrySHA256') != parent.get('parentGeometrySHA256')
                or binding.get('geometrySHA256') != part.get('geometrySHA256')
                or binding.get('cells') != part.get('cells')):
            raise ValueError(f'Invalid shared-datum parent link for {part_id}.')
    return proof


def _read_pack(path):
    html = Path(path).read_text(encoding='utf-8')
    match = re.search(r'<script\b[^>]*\bid="soma-v53-embedded-pack"[^>]*>([\s\S]*?)</script>', html)
    if not match:
        raise ValueError('Embedded source geometry pack not found.')
    return json.loads(gzip.decompress(base64.b64decode(match[1])))


def _read_building_relations(path):
    import osmium

    class Relations(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.rows = []

        def relation(self, relation):
            tags = dict(relation.tags)
            if tags.get('type') == 'building':
                self.rows.append({'id': relation.id, 'tags': tags, 'members': [
                    {'type': member.type, 'ref': member.ref, 'role': member.role}
                    for member in relation.members]})

    handler = Relations()
    handler.apply_file(str(path), locations=False)
    return sorted(handler.rows, key=lambda row: row['id'])


def _file_sha256(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT/'game/baseline/v66.html')
    parser.add_argument('--output', type=Path, default=ROOT/'game/data/v69/building-parts.json')
    parser.add_argument('--pbf', type=Path, help='Read building relations from a PBF verified against the embedded source SHA256.')
    parser.add_argument('--relations', type=Path)
    parser.add_argument('--relations-source-sha')
    args = parser.parse_args()
    pack = _read_pack(args.baseline)
    if args.pbf:
        if args.relations or args.relations_source_sha:
            parser.error('--pbf cannot be combined with separately supplied relation evidence.')
        relations_sha = _file_sha256(args.pbf)
        _collect(pack['records'], relations_sha)
        relations = _read_building_relations(args.pbf)
    else:
        relations = json.loads(args.relations.read_text(encoding='utf-8')) if args.relations else []
        relations_sha = args.relations_source_sha
    proof = generate_parts(pack['records'], relations=relations, relations_source_sha=relations_sha)
    loadproof(proof, pack['records'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output': str(args.output), **proof['statistics'], 'proofSHA256': proof['proofSHA256']}))


if __name__ == '__main__':
    main()
