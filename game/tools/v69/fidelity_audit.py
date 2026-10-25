#!/usr/bin/env python3
"""Audit the delivered geographic baseline; never infer metropolitan completion.

Python's standard library verifies and decodes the immutable source artifacts.
Node executes the actual delivered dimension, terrain and navigation cores.
Node is a development-tool prerequisite, not a prerequisite for playing the game.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE_SHA256 = "f1a6ce4b5957f634ff9fdbfaccfcf11c9e0d22159d01758dd56e29513581a014"
MAX_EMBEDDED_BYTES = 256 * 1024 * 1024
LAYERS = {"buildings", "hydrography", "landuse", "pois", "rail", "roads"}


class AuditError(ValueError):
    """An inconsistent or unverifiable input cannot produce a fidelity report."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_verified_baseline(path: Path) -> tuple[str, dict]:
    raw = path.read_bytes()
    if digest(raw) != BASELINE_SHA256:
        raise AuditError("Baseline v0.66 différente de la livraison vérifiée.")
    return raw.decode("utf-8"), {"file": "game/baseline/v66.html", "bytes": len(raw), "sha256": digest(raw)}


def script_block(html: str, script_id: str) -> tuple[str, str]:
    pattern = re.compile(r"<script\b([^>]*\bid=[\"']" + re.escape(script_id) + r"[\"'][^>]*)>(.*?)</script>", re.S)
    matches = pattern.findall(html)
    if len(matches) != 1:
        raise AuditError(f"Script absent ou dupliqué : {script_id}")
    return matches[0]


def decode_blob(html: str, script_id: str) -> tuple[dict, dict]:
    attributes, body = script_block(html, script_id)
    attrs = dict(re.findall(r"([\w:-]+)=[\"']([^\"']*)[\"']", attributes))
    if attrs.get("data-encoding") != "gzip-base64":
        raise AuditError(f"Encodage non pris en charge : {script_id}")
    try:
        size = int(attrs["data-bytes"])
        expected_hash = attrs["data-sha256"]
        if not 0 < size <= MAX_EMBEDDED_BYTES or not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
            raise ValueError("taille/empreinte")
        compressed = base64.b64decode("".join(body.split()), validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
            raw = stream.read(size + 1)
        if len(raw) != size or digest(raw) != expected_hash:
            raise AuditError(f"Empreinte ou taille du contenu différente : {script_id}")
        payload = json.loads(raw)
    except AuditError:
        raise
    except (ValueError, KeyError, OSError, EOFError) as error:
        raise AuditError(f"Contenu embarqué invalide : {script_id}") from error
    if not isinstance(payload, dict):
        raise AuditError(f"Objet JSON attendu : {script_id}")
    return payload, {"bytes": len(raw), "sha256": digest(raw)}


def core_sources(html: str) -> dict[str, str]:
    ids = {"57": "soma-v57-core", "53": "soma-v53-core", "59": "soma-v59-core",
           "50": "soma-v50-playable-truth-cells", "56": "soma-v56-terrain-core",
           "63": "soma-v63-nav-core"}
    result = {key: script_block(html, script_id)[1] for key, script_id in ids.items()}
    marker = "\n(function(){"
    if marker not in result["50"]:
        raise AuditError("Séparation du noyau v50 inattendue.")
    result["50"] = result["50"].split(marker, 1)[0]
    return result


def finite_bounds(value) -> bool:
    return (isinstance(value, list) and len(value) == 4
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)
            and value[0] < value[2] and value[1] < value[3])


def collect_sources(pack: dict) -> tuple[dict, list[dict], list[dict]]:
    if pack.get("schema") != "soma-massilia/geodata-pack/4" or not isinstance(pack.get("records"), list) or not pack["records"]:
        raise AuditError("Pack géographique v4 non vide attendu.")
    if pack.get("testOnly"):
        raise AuditError("Une fixture ne peut pas être comptée comme couverture réelle.")
    unique, cell_ids, boxes = {}, set(), set()
    fragments, objects_cells = Counter(), defaultdict(set)
    roads_records, all_bounds = [], []
    for record in pack["records"]:
        cell_id, bounds = record.get("cellId"), record.get("boundsL93")
        if not isinstance(cell_id, str) or cell_id in cell_ids or not finite_bounds(bounds):
            raise AuditError("Identifiant ou emprise de cellule invalide/dupliquée.")
        if abs(bounds[2] - bounds[0] - 250) > 1e-6 or abs(bounds[3] - bounds[1] - 250) > 1e-6:
            raise AuditError("Cellule métrique de 250 m attendue.")
        if all_bounds and any(abs((bounds[axis] - all_bounds[0][axis]) / 250 - round((bounds[axis] - all_bounds[0][axis]) / 250)) > 1e-8 for axis in (0, 1)):
            raise AuditError("Cellule décalée du carroyage métrique commun.")
        if tuple(bounds) in boxes:
            raise AuditError("Deux cellules occupent la même emprise.")
        if record.get("v53Synthetic") or record.get("testOnly"):
            raise AuditError("Une fixture ne peut pas être comptée comme couverture réelle.")
        cell_ids.add(cell_id); boxes.add(tuple(bounds)); all_bounds.append(bounds)
        features = record.get("featureCollection", {}).get("features")
        if not isinstance(features, list):
            raise AuditError("Collection de cellule invalide.")
        road_features = []
        for feature in features:
            props = feature.get("properties")
            if not isinstance(props, dict):
                raise AuditError("Propriétés d’objet absentes.")
            source_id = props.get("canonical_id") or feature.get("id")
            layer = props.get("soma:layer") or props.get("logical_layer")
            if not isinstance(source_id, str) or layer not in LAYERS:
                raise AuditError("Identifiant canonique ou couche invalide.")
            small = {key: value for key, value in props.items() if key not in {"soma:mesh53", "soma:metricGeometry"}}
            if source_id in unique and (unique[source_id]["p"] != small or unique[source_id]["layer"] != layer):
                raise AuditError(f"Objet canonique contradictoire : {source_id}")
            unique.setdefault(source_id, {"id": source_id, "layer": layer, "p": small})
            fragments[layer] += 1; objects_cells[source_id].add(cell_id)
            if layer == "roads":
                road_features.append({"id": feature["id"], "properties": {**small, "soma:metricGeometry": props.get("soma:metricGeometry")}})
        roads_records.append({"cellId": cell_id, "boundsL93": bounds, "v53Validated": True,
                              "v53Synthetic": False, "sourceReceipt": record["sourceReceipt"],
                              "featureCollection": {"features": road_features}})
    bounds = [min(b[0] for b in all_bounds), min(b[1] for b in all_bounds),
              max(b[2] for b in all_bounds), max(b[3] for b in all_bounds)]
    counts = Counter(row["layer"] for row in unique.values())
    cells = {"count": len(cell_ids), "boundsL93": bounds, "areaKm2": len(cell_ids) * .0625,
             "envelopeKm2": (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / 1e6,
             "unique": len(unique), "fragments": sum(fragments.values()), "counts": dict(counts),
             "fragmentsByLayer": dict(fragments), "multiCellObjects": sum(len(c) > 1 for c in objects_cells.values()),
             "multiCellBuildings": sum(row["layer"] == "buildings" and len(objects_cells[oid]) > 1 for oid, row in unique.items()),
             "propertiesContradictions": 0}
    return cells, list(unique.values()), roads_records


def terrain_statistics(pack: dict) -> dict:
    try:
        header = json.loads(pack["gridHeader"])
        if any(not isinstance(header.get(key), int) or isinstance(header[key], bool) or not 2 <= header[key] <= 65536 for key in ("rows", "cols")):
            raise ValueError("dimensions du raster")
        if header["rows"] * header["cols"] > 4_000_000:
            raise ValueError("budget du raster")
        data = base64.b64decode(pack["dataBase64"], validate=True)
        mask = base64.b64decode(pack["maskBase64"], validate=True)
        expected = header["rows"] * header["cols"]
        if len(data) != expected * 4 or len(mask) != expected or any(m not in (0, 1) for m in mask):
            raise ValueError("taille du raster")
        values = [value[0] for value in struct.iter_unpack("<f", data)]
        valid = [v for v, m in zip(values, mask) if m]
        if not valid or not all(math.isfinite(v) for v in valid):
            raise ValueError("altitude non finie")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AuditError("Grille de relief invalide.") from error
    return {"gridHeader": header, "declaredSHA256": pack.get("sha256"), "computedNodes": expected,
            "computedValid": len(valid), "computedNoData": expected - len(valid),
            "computedMinM": min(valid), "computedMaxM": max(valid),
            "meaning": "Espacement de mesures, pas précision garantie des rues ou ouvrages.",
            "legacyStatisticsDiffer": pack.get("statistics") != pack.get("stats")}


_NODE = r"""
'use strict';
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context={console,Math,atob,TextEncoder};context.window=context;vm.createContext(context);
for(const key of ['57','53','59','50','56','63'])vm.runInContext(input.scripts[key],context,{filename:'source-core-'+key+'.js'});
const K=context.__SOMA_FIDELITY59_CORE__,C=context.__SOMA_V53_CORE__,F=context.__SOMA_V50_CORE__;
const count=values=>{const out={};for(const value of values)out[value]=(out[value]||0)+1;return out;};
const pct=(n,d)=>Math.round(n/d*1000000)/10000;
const dimensions=row=>{const p=row.p,ref=K.canApplyHeight(p,row.ign)?row.ign:null;return K.dimension(p,F.buildingHeight(p,row.id),ref);};
if(input.operation==='dimensions'){
 process.stdout.write(JSON.stringify(input.rows.map(dimensions)));process.exit(0);
}
const unique=input.unique,buildings=unique.filter(f=>f.layer==='buildings'),roads=unique.filter(f=>f.layer==='roads');
const dims=buildings.map(f=>dimensions({...f,ign:input.fidelity.buildings[f.id]}));
const height=count(dims.map(d=>d.heightSource)),tagPresence={};
const isPart=p=>p['building:part']!=null&&!['','no','false','0'].includes(String(p['building:part']).toLowerCase());
for(const tag of ['height','min_height','building:levels','building:min_level','building:part','building:material','building:colour','roof:shape','roof:height','roof:direction','roof:orientation','roof:material','roof:colour'])tagPresence[tag]=buildings.filter(f=>Object.hasOwn(f.p,tag)).length;
const declared=(height['osm-height']||0)+(height['ign-bdtopo-height']||0);
const b={unique:buildings.length,sourceHeightDistribution:height,
 sourceHeightPercent:Object.fromEntries(Object.entries(height).map(([k,n])=>[k,pct(n,buildings.length)])),
 validDimensions:dims.filter(d=>d.valid).length,invalidDimensions:dims.filter(d=>!d.valid).length,
 tagPresence,roofShapes:count(buildings.filter(f=>f.p['roof:shape']).map(f=>String(f.p['roof:shape']))),
 activeBuildingParts:buildings.filter(f=>isPart(f.p)).length,
 sourceHeightByObjectKind:{buildingParts:count(buildings.flatMap((f,i)=>isPart(f.p)?[dims[i].heightSource]:[])),
 otherBuildingObjects:count(buildings.flatMap((f,i)=>!isPart(f.p)?[dims[i].heightSource]:[]))},
 fullyTaggedSkillionCount:buildings.filter(f=>f.p['roof:shape']==='skillion'&&K.measure(f.p.height)>0&&K.measure(f.p['roof:height'])>0&&Object.hasOwn(f.p,'roof:direction')&&Number.isFinite(Number(f.p['roof:direction']))).length,
 declaredHeightOrIGN:declared,declaredHeightOrIGNPercent:pct(declared,buildings.length),
 meaning:'Height declarations or matched IGN references are not a certification of complete architecture.'};
const profiles=roads.map(f=>({...f,q:input.fidelity.roadMetadata[f.id]||K.roadProfile(f.p)}));
const active=v=>v!=null&&!['','no','false','0'].includes(String(v).toLowerCase());
const conflict=profiles.filter(f=>!f.q.structural&&(active(f.p.indoor)||active(f.p.covered)));
const widths=count(profiles.map(f=>f.q.widthSource));
const r={unique:roads.length,widthDistribution:widths,widthPercent:Object.fromEntries(Object.entries(widths).map(([k,n])=>[k,pct(n,roads.length)])),
 structuralExcluded:profiles.filter(f=>f.q.structural).length,indoor:profiles.filter(f=>active(f.p.indoor)).length,
 covered:profiles.filter(f=>active(f.p.covered)).length,indoorOrCovered:profiles.filter(f=>active(f.p.indoor)||active(f.p.covered)).length,
 indoorCoveredClassifiedAsNonStructural:conflict.length,
 indoorCoveredExamples:conflict.slice(0,12).map(f=>({id:f.id,indoor:f.p.indoor,covered:f.p.covered,highway:f.p.highway})),
 uniqueSteps:profiles.filter(f=>f.p.highway==='steps').length,
 stepsWithDeclaredStepCount:profiles.filter(f=>f.p.highway==='steps'&&Object.hasOwn(f.p,'step_count')).length,
 stepsWithIncline:profiles.filter(f=>f.p.highway==='steps'&&Object.hasOwn(f.p,'incline')).length,
 sidewalkDeclaredRoads:profiles.filter(f=>f.q.sidewalk.known).length,
 sidewalkDeclaredSides:profiles.reduce((n,f)=>n+!!f.q.sidewalk.left+!!f.q.sidewalk.right,0),
 supportedSidewalkDeclaredSides:profiles.filter(f=>!f.q.structural).reduce((n,f)=>n+!!f.q.sidewalk.left+!!f.q.sidewalk.right,0)};
const nav=input.navigation;context.__SOMA_NAV63_CORE__.validate(nav);
const navigation={nodes:nav.nodes.length,edges:nav.edges.length,ways:Object.keys(nav.ways).length,turnRestrictions:nav.turns.length,
 footSegments:nav.edges.filter(e=>e[4]&3).length,carSegments:nav.edges.filter(e=>e[4]&12).length,
 crossCellSegments:nav.edges.filter(e=>e[6].length>1).length,stepsSegments:nav.edges.filter(e=>e[5]).length,policy:nav.policy};
const grid=context.__SOMA_TERRAIN56_CORE__.load(input.terrain,input.boundsL93);
let neighborPairs=0,withSeam=0,seamPairs=0,oneWayOnly=0,maxMismatch=0;
for(let i=0;i<input.records.length;i++)for(let j=i+1;j<input.records.length;j++){
 const a=input.records[i],b=input.records[j],A=a.boundsL93,B=b.boundsL93;let sides=null;
 if(Math.abs(A[2]-B[0])<1e-6&&Math.abs(A[1]-B[1])<1e-6)sides=['E','W'];
 else if(Math.abs(B[2]-A[0])<1e-6&&Math.abs(A[1]-B[1])<1e-6)sides=['W','E'];
 else if(Math.abs(A[3]-B[1])<1e-6&&Math.abs(A[0]-B[0])<1e-6)sides=['N','S'];
 else if(Math.abs(B[3]-A[1])<1e-6&&Math.abs(A[0]-B[0])<1e-6)sides=['S','N'];
 if(!sides)continue;neighborPairs++;const seams=C.matchSeams(a,b,...sides);seamPairs+=seams.length;if(seams.length)withSeam++;
 for(const seam of seams){if(seam.canAtoB!==seam.canBtoA)oneWayOnly++;maxMismatch=Math.max(maxMismatch,seam.delta);}
}
const box=input.boundsL93,corners=[[box[0],box[1]],[box[0],box[3]],[box[2],box[1]],[box[2],box[3]]].map(C.inverse);
process.stdout.write(JSON.stringify({buildings:b,roads:r,navigation,
 terrainCoreValidated:true,terrainCoreStats:grid.stats,
 boundsWGS84:[Math.min(...corners.map(p=>p[0])),Math.min(...corners.map(p=>p[1])),Math.max(...corners.map(p=>p[0])),Math.max(...corners.map(p=>p[1]))],
 cellSeams:{geometricNeighborPairs:neighborPairs,neighborPairsWithNativeRoadSeam:withSeam,matchedRoadEndpointPairs:seamPairs,
 oneWayOnlyPairs:oneWayOnly,maxMismatchM:maxMismatch,thresholdM:C.EPS,
 runtimeReachabilityVerified:false,
 meaning:'Compatible source endpoints under frozen v53 rules; not verified surface reachability, bridge access or all walkable boundary crossings.'}}));
"""


def run_cores(scripts: dict[str, str], payload: dict, node: str | None = None):
    executable = node or shutil.which("node")
    if not executable:
        raise AuditError("Node.js est nécessaire pour cet audit de développement, pas pour jouer.")
    try:
        result = subprocess.run([executable, "-e", _NODE], input=json.dumps({"scripts": scripts, **payload}),
                                text=True, capture_output=True, check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AuditError("Impossible d’exécuter les noyaux JavaScript livrés.") from error
    if result.returncode:
        raise AuditError("Un noyau livré refuse les données : " + result.stderr.strip()[:2000])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AuditError("Résultat des noyaux JavaScript invalide.") from error


def territory_summary(path: Path | None) -> dict:
    summary = {"name": "Métropole Aix-Marseille-Provence", "inseeSiren": "200054807",
               "communeCount": None, "boundaryValidated": False, "coverageRatio": None,
               "meaning": "No metropolitan completion ratio without a validated complete territorial boundary."}
    if path is None or not path.is_file():
        return summary
    try:
        raw = path.read_bytes()
        territory = json.loads(raw)
        communes = territory["communes"]
        if territory.get("schema") != "soma-metropole/territory/1" or territory.get("id") != "200054807" or not isinstance(communes, list) or len(communes) != 92:
            raise ValueError("périmètre ou liste des communes")
        codes = [commune["code"] for commune in communes]
        if len(set(codes)) != 92 or any(not isinstance(code, str) or not re.fullmatch(r"\d{5}", code) for code in codes):
            raise ValueError("codes de commune")
    except (KeyError, TypeError, ValueError) as error:
        raise AuditError("Référence territoriale AMP 2026 invalide ou incomplète.") from error
    summary.update({"name": territory["name"], "year": territory.get("year"), "communeCount": len(communes),
                    "communeCodes": sorted(codes), "boundaryProvided": territory.get("boundary") is not None,
                    "membershipSource": territory.get("source"),
                    "membershipFile": {"file": "game/data/v69/territory.json", "bytes": len(raw), "sha256": digest(raw)}})
    return summary


def create_report(baseline: Path, terrain_path: Path, navigation_path: Path, node: str | None = None,
                  territory_path: Path | None = None) -> dict:
    html, baseline_info = read_verified_baseline(baseline)
    pack, pack_info = decode_blob(html, "soma-v53-embedded-pack")
    fidelity, fidelity_info = decode_blob(html, "soma-v59-fidelity-data")
    if fidelity.get("basePackSHA256") != pack_info["sha256"]:
        raise AuditError("Complément de fidélité lié à un autre pack géographique.")
    try:
        terrain_raw, nav_raw = terrain_path.read_bytes(), navigation_path.read_bytes()
        terrain, nav = json.loads(terrain_raw), json.loads(nav_raw)
    except (OSError, json.JSONDecodeError) as error:
        raise AuditError("Relief ou navigation JSON illisible.") from error
    if nav.get("sourcePackSHA256") != pack_info["sha256"] or nav.get("sourcePbfSHA256") != pack.get("sourceReceipt", {}).get("sha256"):
        raise AuditError("Navigation liée à une autre source géographique.")
    cells, unique, records = collect_sources(pack)
    expected_hashes = {record["cellId"]: record["contentSHA256"] for record in pack["records"]}
    if nav.get("cellHashes") != expected_hashes:
        raise AuditError("Empreintes des cellules de navigation différentes du pack.")
    terrain_summary = terrain_statistics(terrain)
    computed = run_cores(core_sources(html), {"operation": "audit", "unique": unique, "records": records,
                         "fidelity": {key: fidelity[key] for key in ("buildings", "roadMetadata")}, "navigation": nav, "terrain": terrain,
                         "boundsL93": cells["boundsL93"]}, node)
    cells["boundsWGS84"] = computed.pop("boundsWGS84")
    terrain_summary["sourceCoreValidated"] = computed.pop("terrainCoreValidated")
    terrain_summary["sourceCoreStats"] = computed.pop("terrainCoreStats")
    return {"schema": "soma/fidelity-audit/1", "version": "0.69.0",
            "auditScope": {"kind": "frozen-delivery-baseline", "sourceEdition": "0.67 (frozen v0.66 geographic baseline)",
                           "activeV69CorrectionsIncluded": False,
                           "meaning": "Inventory of source evidence before v0.69 corrections, not a certification of the active renderer."},
            "requestedTerritory": territory_summary(territory_path),
            "sourceFiles": {"baseline": baseline_info, "uncompressedPack": pack_info,
                            "uncompressedFidelityOverlay": fidelity_info,
                            "terrain": {"file": "game/data/v58/terrain.ign.json", "bytes": len(terrain_raw), "sha256": digest(terrain_raw)},
                            "navigation": {"file": "game/data/v63/navigation.json", "bytes": len(nav_raw), "sha256": digest(nav_raw)}},
            "sourceReceipt": pack["sourceReceipt"], "cells": cells, "terrain": terrain_summary, **computed,
            "certification": {"certifiedCells": 0, "completeMarseille": False, "completeMetropoleAMP": False,
                              "independentSourceAuthenticityVerified": False,
                              "meaning": "Source integrity and internal consistency do not prove surveyed 1:1 architecture or full territorial coverage."}}


def write_report(report: dict, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "game/baseline/v66.html")
    parser.add_argument("--terrain", type=Path, default=ROOT / "game/data/v58/terrain.ign.json")
    parser.add_argument("--navigation", type=Path, default=ROOT / "game/data/v63/navigation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "game/data/v69/FIDELITY_REPORT.json")
    parser.add_argument("--territory", type=Path, default=ROOT / "game/data/v69/territory.json")
    parser.add_argument("--node", help="Chemin du binaire Node.js de développement")
    args = parser.parse_args()
    try:
        report = create_report(args.baseline, args.terrain, args.navigation, args.node, args.territory)
        write_report(report, args.output)
    except (AuditError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Audit impossible : {error}\n")
    print(json.dumps({"report": str(args.output), "cells": report["cells"]["count"],
                      "buildings": report["buildings"]["unique"], "completeMetropoleAMP": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
