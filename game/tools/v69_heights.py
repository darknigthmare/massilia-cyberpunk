"""Bounded, source-bound delivery of measured IGN eave references (stdlib only)."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.metropole.building_heights import (
    HASH, HeightMatchError, _osm_priority, canonical, digest, validate_matches,
)

EXPECTED_PARENT_SHA256 = '603e851584a688cc5d59182b1d1719bb53683299bf40da85e82deb9a6fcbbf07'
MAX_COMPRESSED = 16 * 1024 * 1024
MAX_DECODED = 64 * 1024 * 1024
MAX_MATCHES = 100000
HEIGHT_KIND = 'eaves'
ACCURACY = 'source-match-not-certified'
ROOF_POLICY = 'flat-approximation-without-explicit-osm-total-height'


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result or key in {'__proto__', 'prototype', 'constructor'}:
            raise HeightMatchError('Duplicate or forbidden height-proof JSON key.')
        result[key] = value
    return result


def _parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError) as error:
        raise HeightMatchError('Invalid or non-finite height-proof JSON.') from error


def compact_matches(path, *, expected_sha=EXPECTED_PARENT_SHA256):
    """Retain all accepted evidence and metadata; omit only rejected row payloads."""
    path = Path(path)
    if path.stat().st_size > MAX_DECODED:
        raise HeightMatchError('Parent matching proof exceeds the byte budget.')
    raw = path.read_bytes()
    parent_sha = hashlib.sha256(raw).hexdigest()
    if parent_sha != expected_sha:
        raise HeightMatchError('Parent matching proof SHA256 differs from its pinned source.')
    parent = validate_matches(_parse(raw))
    proof = {key:value for key,value in parent.items() if key not in {'rejected', 'proofSHA256'}}
    proof.update(parentMatchingProofSHA256=parent_sha, parentProofContentSHA256=parent['proofSHA256'],
                 rejectedRowsOmitted=len(parent.get('rejected', [])), heightKind=HEIGHT_KIND,
                 accuracy=ACCURACY, roofSurveyed=False, roofGeometryPolicy=ROOF_POLICY)
    proof['proofSHA256'] = digest(proof)
    validate_matches(proof)
    return proof


def validate_height_bindings(proof, records, *, source_sha=None, expected_parent_sha=EXPECTED_PARENT_SHA256):
    """Check every saved fragment binding against the immutable source records."""
    validate_matches(proof)
    if (proof.get('parentMatchingProofSHA256') != expected_parent_sha or
            not isinstance(proof.get('parentProofContentSHA256'), str) or not HASH.fullmatch(proof['parentProofContentSHA256']) or
            proof.get('heightKind') != HEIGHT_KIND or proof.get('accuracy') != ACCURACY or
            proof.get('roofSurveyed') is not False or proof.get('roofGeometryPolicy') != ROOF_POLICY):
        raise HeightMatchError('Height-reference origin or eave/roof semantics differ.')
    matches = proof['matches']
    statistics = proof.get('statistics', {})
    if (len(matches)>MAX_MATCHES or statistics.get('accepted')!=len(matches) or
            proof.get('rejectedRowsOmitted')!=statistics.get('rejected') or 'rejected' in proof):
        raise HeightMatchError('Compact height-proof counts or omitted rows differ.')
    source = proof['sourceSHA256']
    if source_sha is not None and source_sha != source:
        raise HeightMatchError('Height proof belongs to another source PBF snapshot.')
    by_id = {}
    for row in matches.values():
        identity, cells = row['canonicalId'], row.get('cells')
        if (row.get('decision')!='accepted-conservative-match' or row.get('heightSource')!='ign-bdtopo-height' or
                row.get('method')!='footprint-iou-unique-reciprocal' or identity in by_id or not isinstance(cells, dict) or not cells or any(
                not isinstance(cell,str) or not isinstance(sha,str) or not HASH.fullmatch(sha) for cell,sha in cells.items())):
            raise HeightMatchError('Duplicate height identity or incomplete fragment bindings.')
        by_id[identity] = row
    observed = {identity:{} for identity in by_id}
    seen = set()
    values = records.values() if isinstance(records, dict) else records
    for index, record in enumerate(values):
        if index>=100000 or not isinstance(record, dict) or any(record.get(key) for key in ('v53Synthetic','v50Synthetic','testOnly')):
            raise HeightMatchError('Only bounded real source records can bind heights.')
        cell, cell_sha = record.get('cellId'), record.get('contentSHA256')
        if (not isinstance(cell,str) or cell in seen or not isinstance(cell_sha,str) or not HASH.fullmatch(cell_sha) or
                record.get('sourceReceipt',{}).get('sha256') != source):
            raise HeightMatchError('Height-proof source cell identity/content/source differs.')
        seen.add(cell)
        collection = record.get('featureCollection', {})
        if not isinstance(collection,dict) or collection.get('type')!='FeatureCollection' or not isinstance(collection.get('features'),list):
            raise HeightMatchError('Source building feature collection is missing.')
        for feature in collection['features']:
            p = feature.get('properties', {}) if isinstance(feature,dict) else {}
            if not isinstance(p,dict) or p.get('soma:layer')!='buildings':
                continue
            identity = p.get('canonical_id') or feature.get('id')
            row = by_id.get(identity)
            if row is None:
                continue
            if p.get('soma:geometry_sha256') != row['geometrySHA256']:
                raise HeightMatchError('Height-proof geometry differs from the source feature.')
            priority = _osm_priority(p)
            if priority is not None:
                raise HeightMatchError('An IGN height cannot override the source policy: '+priority)
            observed[identity][cell] = cell_sha
    if not seen:
        raise HeightMatchError('Original source records are required for height references.')
    for identity, row in by_id.items():
        if observed[identity] != row['cells']:
            raise HeightMatchError('Height-proof cells/content hashes or source feature are incomplete: '+identity)
    return proof


def load_height_matches(path, *, records, source_sha=None, expected_parent_sha=EXPECTED_PARENT_SHA256):
    path = Path(path)
    if path.stat().st_size > MAX_COMPRESSED:
        raise HeightMatchError('Compressed height proof exceeds its byte budget.')
    try:
        with gzip.open(path, 'rb') as stream:
            raw = stream.read(MAX_DECODED+1)
    except (OSError, EOFError) as error:
        raise HeightMatchError('Invalid gzip height proof.') from error
    if len(raw)>MAX_DECODED:
        raise HeightMatchError('Decoded height proof exceeds its byte budget.')
    return validate_height_bindings(_parse(raw),records,source_sha=source_sha,expected_parent_sha=expected_parent_sha)


def encoded_proof(proof):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0, compresslevel=9) as stream:
        stream.write(canonical(proof).encode('utf-8'))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compact-original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    proof = compact_matches(args.compact_original)
    raw = encoded_proof(proof)
    if args.output.exists():
        if args.output.read_bytes()!=raw:
            parser.exit(1,'Refusing to overwrite different height-reference data.\n')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(raw)
    print(json.dumps({'measuredReferences':len(proof['matches']),'bytes':len(raw),
                      'proofSHA256':proof['proofSHA256'],'heightKind':HEIGHT_KIND,'roofSurveyed':False}))


if __name__=='__main__':
    main()
