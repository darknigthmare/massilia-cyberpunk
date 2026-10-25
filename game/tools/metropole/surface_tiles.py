"""Prepare metric road-surface sidecars for source-preserving vector tiles.

Only this optional generator imports GIS packages. The game receives checked
gzip/JSON assets. Road dimensions are evaluated by the actual frozen v59
JavaScript core, not a Python approximation. Full native axes are buffered before
cell clipping; mapped road areas retain their original polygon holes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

MANIFEST_SCHEMA = "soma-metropole/surface-tiles/1"
CELL_SCHEMA = "soma-metropole/surface-cell/1"
LAYERS = ("road", "unsealed", "paved", "foot", "walk", "mark")
VERSION = "0.69.0"


class SurfaceFailure(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_asset(base, descriptor, maximum=512 * 1024 * 1024):
    if not isinstance(descriptor, dict) or descriptor.get("encoding") != "gzip-json":
        raise SurfaceFailure("A checked gzip-json source asset is required")
    relative = descriptor.get("path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise SurfaceFailure("Source assets need relative paths")
    path = (Path(base) / relative).resolve()
    if not path.is_relative_to(Path(base).resolve()):
        raise SurfaceFailure("Source asset escapes its vector package")
    if path.stat().st_size != descriptor.get("bytes") or file_sha256(path) != descriptor.get("sha256"):
        raise SurfaceFailure("Source asset checksum or size differs from its manifest")
    with gzip.open(path, "rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum or ("decodedBytes" in descriptor and descriptor["decodedBytes"] != len(raw)):
        raise SurfaceFailure("Source asset exceeds or contradicts its decoded-byte budget")
    return json.loads(raw)


def write_asset(path, value, maximum):
    raw = canonical(value)
    if len(raw) > maximum:
        raise SurfaceFailure("Generated surface cell exceeds its decoded-byte budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, filename="", mode="wb", mtime=0, compresslevel=6) as compressed:
            compressed.write(raw)
    return {"path": path.name, "encoding": "gzip-json", "bytes": path.stat().st_size,
            "decodedBytes": len(raw), "sha256": file_sha256(path)}


def profile_sources(roads, buildings, baseline, node=None, batch_size=4096):
    """Evaluate true v59 dimensions in bounded batches of canonical objects."""
    node = node or shutil.which("node")
    if not node:
        raise SurfaceFailure("Node is required to evaluate the frozen v59 dimension core")
    baseline = Path(baseline)
    html = baseline.read_text(encoding="utf-8")
    pattern = re.compile(r'<script\b[^>]*\bid="soma-v59-core"[^>]*>(.*?)</script>', re.S)
    matches = pattern.findall(html)
    if len(matches) != 1:
        raise SurfaceFailure("The verified baseline must contain exactly one soma-v59-core script")
    source = matches[0]
    runner = r"""
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8')),context={window:{}};
vm.runInNewContext(input.source,context,{filename:'soma-v59-core.js'});
const core=context.window.__SOMA_FIDELITY59_CORE__;
if(core?.version!=='0.59.0'||typeof core.roadProfile!=='function'||typeof core.dimension!=='function')throw Error('Unsupported frozen dimension core');
const roads={},buildings={};
for(const[id,p]of Object.entries(input.roads))roads[id]=core.roadProfile(p);
for(const[id,p]of Object.entries(input.buildings)){
 const q=core.dimension(p,0,null);
 buildings[id]={minHeight:q.minHeight,openStructure:q.openStructure};
}
process.stdout.write(JSON.stringify({roads,buildings}));
"""
    if not isinstance(batch_size, int) or batch_size < 1:
        raise SurfaceFailure("A positive dimension batch size is required")
    profiles = {"roads": {}, "buildings": {}}
    evaluated = False
    for kind, values in (("roads", roads), ("buildings", buildings)):
        items = iter(values.items())
        while True:
            from itertools import islice
            batch = dict(islice(items, batch_size))
            if not batch:
                break
            request = {"source": source, "roads": {}, "buildings": {}, kind: batch}
            result = subprocess.run([str(node), "-e", runner], input=canonical(request), capture_output=True, timeout=120)
            if result.returncode:
                raise SurfaceFailure("Frozen v59 dimension evaluation failed: " + result.stderr.decode("utf-8", errors="replace")[:1500])
            profiles[kind].update(json.loads(result.stdout)[kind])
            evaluated = True
    if not evaluated:
        result = subprocess.run([str(node), "-e", runner], input=canonical({"source": source, "roads": {}, "buildings": {}}),
                                capture_output=True, timeout=120)
        if result.returncode:
            raise SurfaceFailure("Frozen v59 dimension evaluation failed: " + result.stderr.decode("utf-8", errors="replace")[:1500])
    return profiles, {"scriptId": "soma-v59-core", "version": "0.59.0",
                      "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                      "baselineSHA256": file_sha256(baseline)}


def _gis():
    from pyproj import Transformer
    from shapely.affinity import affine_transform
    from shapely.geometry import LineString, Polygon, box, shape, mapping
    from shapely.ops import transform, unary_union
    try:
        from .road_surfaces import _triangles, withheld_reasons
    except ImportError:
        from road_surfaces import _triangles, withheld_reasons
    return Transformer, affine_transform, LineString, Polygon, box, shape, mapping, transform, unary_union, _triangles, withheld_reasons


def exclusions(properties, profile):
    *_, withheld_reasons = _gis()
    result = withheld_reasons(properties)
    if str(properties.get("location", "")).strip().lower() in ("underground", "underwater", "overground"):
        result.append("unmodelled-location")
    if properties.get("highway") in ("construction", "proposed", "elevator"):
        result.append("non-surface-or-unbuilt-highway")
    if profile.get("structural") and not result:
        result.append("v59-structural-profile")
    return result


def _parts(geometry, types):
    if geometry.is_empty:
        return []
    if geometry.geom_type in types:
        return [geometry]
    if hasattr(geometry, "geoms"):
        return [part for item in geometry.geoms for part in _parts(item, types)]
    return []


def _polygonal(geometry):
    """Discard dimension-zero/one overlay debris without moving any vertices.

    Even unions of valid polygons can return a GeometryCollection containing
    boundary lines at floating point coincidences. GEOS cannot reliably overlay
    mixed dimensions (including EMPTY minus that collection). These lines have
    zero pavement area and must never become the next layer's occlusion mask.
    Parts from an overlay result are already disjoint; do not re-union them.
    """
    from shapely.geometry import MultiPolygon, Polygon
    parts = _parts(geometry, {"Polygon"})
    return parts[0] if len(parts) == 1 else MultiPolygon(parts) if parts else Polygon()


def road_bands(geometry, profile):
    """Return carriageway and explicit sidewalk polygons, before ANY clipping."""
    *_, union, _, _ = _gis()
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        # An area:highway polygon already describes its surface. It must not be
        # enlarged by a guessed width or ring-buffered into an invented sidewalk.
        return geometry, union([])
    width = profile.get("width")
    if not isinstance(width, (int, float)) or not math.isfinite(width) or not 0 < width <= 100:
        raise SurfaceFailure("Frozen dimension core returned an invalid road width")
    body, walks = [], []
    sidewalks = profile.get("sidewalk") or {}
    for line in _parts(geometry, {"LineString"}):
        body.append(line.buffer(width / 2, cap_style="flat", join_style="mitre"))
        for side, sign in (("left", 1), ("right", -1)):
            if sidewalks.get(side):
                sw = sidewalks.get(side + "Width")
                if not isinstance(sw, (int, float)) or not math.isfinite(sw) or not 0 < sw <= 8:
                    raise SurfaceFailure("Frozen dimension core returned an invalid sidewalk width")
                outer = line.buffer(sign * (width / 2 + sw), single_sided=True, join_style="mitre")
                inner = line.buffer(sign * width / 2, single_sided=True, join_style="mitre")
                walks.append(outer.difference(inner))
    return union(body), union(walks)


def surface_layer(profile):
    if profile.get("unsealed"):
        return "unsealed"
    if profile.get("surface") in ("paving_stones", "sett", "cobblestone", "cobblestone:flattened", "concrete:plates"):
        return "paved"
    return "foot" if profile.get("foot") else "road"


def cell_surfaces(bounds, layers, occluders, coverage=None):
    """Clip bands and triangulate disjoint layers; also the small-case oracle."""
    _, affine, _, _, box, _, _, _, union, triangles, _ = _gis()
    tile = box(*bounds)
    if coverage is not None:
        tile = coverage.clip(tile) if isinstance(coverage, CoverageClip) else tile.intersection(coverage)
    tile = _polygonal(tile)
    blocked = _polygonal(_polygonal(occluders).intersection(tile))
    ce, cn = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    cell = {"surfaces": {}, "areaM2": {}}
    occupied = _polygonal(union([]))
    # This resolves material overdraw, not traffic priority or turn connectivity.
    # Explicit paving/unsealed tags take precedence over generic class styling.
    for layer in ("paved", "unsealed", "road", "foot", "walk", "mark"):
        source = layers.get(layer, union([]))
        geometry = _polygonal(_polygonal(source).intersection(tile))
        if not geometry.is_empty and not blocked.is_empty:
            geometry = _polygonal(geometry.difference(blocked))
        if not geometry.is_empty and not occupied.is_empty:
            geometry = _polygonal(geometry.difference(occupied))
        polygonal = geometry
        local = affine(polygonal, [1, 0, 0, -1, -ce, cn])
        cell["surfaces"][layer] = triangles(local)
        cell["areaM2"][layer] = polygonal.area
        if not polygonal.is_empty:
            occupied = _polygonal(occupied.union(polygonal))
    cell["surfaces"] = {layer: cell["surfaces"][layer] for layer in LAYERS}
    cell["areaM2"] = {layer: cell["areaM2"][layer] for layer in LAYERS}
    conflict = 0.0
    if not blocked.is_empty:
        pavement = _polygonal(union([layers.get(layer, union([])) for layer in LAYERS]))
        pavement = _polygonal(pavement.intersection(tile))
        if not pavement.is_empty:
            conflict = pavement.intersection(blocked).area
    return cell, {"pavementConflictAreaRemovedM2": conflict, "surfaceAreaM2": occupied.area}


class CoverageClip:
    """Avoid intersecting the complete administrative boundary for interior cells."""

    def __init__(self, geometry):
        from shapely.prepared import prep
        self.geometry = geometry
        self.prepared = prep(geometry)

    def clip(self, tile):
        if self.prepared.covers(tile):
            return tile
        if not self.prepared.intersects(tile):
            return tile.difference(tile)
        return tile.intersection(self.geometry)


class SurfaceSpatialIndex:
    """Index native bands without any constructive union across the territory.

    Union distributes over cell intersection. Clipping only tree candidates
    before their local union preserves holes, material priority and overlaps,
    while bounding GEOS constructive operations by one 250 m cell. Source IDs
    remain associated with bands, including those which only touch a cell edge.
    """

    def __init__(self, layers, occluders):
        from shapely.strtree import STRtree
        self.sources, self.trees = {}, {}
        for layer in LAYERS:
            entries = [(source_id, geometry) for source_id, geometry in layers.get(layer, []) if not geometry.is_empty]
            self.sources[layer] = [source_id for source_id, _ in entries]
            self.trees[layer] = STRtree([geometry for _, geometry in entries])
        self.blockers = STRtree([geometry for geometry in occluders if not geometry.is_empty])
        self.stats = {"algorithm": "native-bands-strtree-per-cell",
                      "layerEntries": {layer: len(self.trees[layer].geometries) for layer in LAYERS},
                      "blockerEntries": len(self.blockers.geometries), "cellsQueried": 0,
                      "candidateEntries": 0, "maxCellCandidates": 0}

    def cell(self, bounds, coverage=None):
        _, _, _, _, box, _, _, _, union, _, _ = _gis()
        tile = box(*bounds)
        layers, source_ids, candidates = {}, set(), 0
        for layer in LAYERS:
            tree = self.trees[layer]
            indices = sorted(tree.query(tile, predicate="intersects")) if len(tree.geometries) else []
            candidates += len(indices)
            source_ids.update(self.sources[layer][i] for i in indices)
            layers[layer] = _polygonal(union([part for i in indices
                                              for part in _parts(tree.geometries[i].intersection(tile), {"Polygon"})]))
        if not candidates:
            # Rural/sea cells need no constructive work on building/water
            # masks when there is no candidate pavement to occlude.
            self.stats["cellsQueried"] += 1
            return ({"surfaces": {layer: [] for layer in LAYERS}, "areaM2": {layer: 0.0 for layer in LAYERS}},
                    {"pavementConflictAreaRemovedM2": 0.0, "surfaceAreaM2": 0.0}, source_ids)
        indices = sorted(self.blockers.query(tile, predicate="intersects"))
        candidates += len(indices)
        blocked = _polygonal(union([part for i in indices
                                   for part in _parts(self.blockers.geometries[i].intersection(tile), {"Polygon"})]))
        self.stats["cellsQueried"] += 1
        self.stats["candidateEntries"] += candidates
        self.stats["maxCellCandidates"] = max(self.stats["maxCellCandidates"], candidates)
        cell, report = cell_surfaces(bounds, layers, blocked, coverage)
        return cell, report, source_ids


def _coverage(manifest, base, to_metric):
    _, _, _, _, box, shape, _, transform, _, _, _ = _gis()
    bounds = manifest.get("bounds")
    extent = box(*bounds) if bounds is not None else None
    boundary = manifest.get("boundary")
    if boundary:
        declared = Path(boundary["path"])
        path = declared if declared.is_absolute() else base / declared
        if file_sha256(path) != boundary.get("sha256"):
            raise SurfaceFailure("Source boundary checksum differs from the vector manifest")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("type") == "FeatureCollection":
            from shapely.ops import unary_union
            geometry = unary_union([shape(f["geometry"]) for f in data["features"]])
        else:
            geometry = shape(data["geometry"] if data.get("type") == "Feature" else data)
        if geometry.geom_type not in ("Polygon", "MultiPolygon") or not geometry.is_valid:
            raise SurfaceFailure("Invalid declared source coverage polygon")
        metric = transform(to_metric.transform, geometry)
        extent = metric if extent is None else extent.intersection(metric)
    return extent


def prepare_surfaces(manifest_path, output, *, baseline=None, node=None, max_tile_bytes=64 * 1024 * 1024, progress=None):
    Transformer, _, LineString, _, box, shape, mapping, _, union, _, _ = _gis()
    manifest_path, output = Path(manifest_path).resolve(), Path(output).absolute()
    if output.exists():
        raise SurfaceFailure("Output already exists; choose a new surface output directory")
    baseline = Path(baseline) if baseline is not None else Path(__file__).resolve().parents[2] / "baseline/v66.html"
    source_manifest_sha = file_sha256(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "soma-metropole/vector-tiles/1" or manifest.get("crs") != "EPSG:2154" or manifest.get("units") != "m":
        raise SurfaceFailure("A Lambert-93 vector manifest is required")
    pbf_sha = manifest.get("source", {}).get("sha256")
    if not isinstance(pbf_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", pbf_sha):
        raise SurfaceFailure("Source PBF fingerprint is missing")
    started = time.monotonic()

    def notify(phase, **details):
        if progress is not None:
            import resource
            progress({"phase": phase, "elapsedSeconds": round(time.monotonic() - started, 3),
                      "peakRssMiB": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1), **details})

    metric = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    records, source, record = {}, {}, None
    for number, descriptor in enumerate(manifest.get("tiles", []), 1):
        record = read_asset(manifest_path.parent, descriptor["vector"], maximum=16 * 1024 * 1024)
        cell_id = record.get("cellId")
        if cell_id in records or cell_id != descriptor.get("cellId") or record.get("boundsL93") != descriptor.get("boundsL93"):
            raise SurfaceFailure("Vector cell identity or bounds disagree with its manifest")
        bounds = record.get("boundsL93")
        if not isinstance(bounds, list) or len(bounds) != 4 or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in bounds) or abs(bounds[2] - bounds[0] - 250) > 1e-6 or abs(bounds[3] - bounds[1] - 250) > 1e-6:
            raise SurfaceFailure("A complete 250 m metric cell definition is required")
        if digest(record["featureCollection"]) != record.get("contentSHA256") or record.get("sourceReceipt", {}).get("sha256") != pbf_sha:
            raise SurfaceFailure("Vector cell content hash or source receipt is inconsistent")
        # Never retain the decoded FeatureCollection. At metropolitan scale its
        # prepared meshes dominate memory and are irrelevant to surface buffers.
        summary = {"boundsL93": bounds, "contentSHA256": record["contentSHA256"], "roads": set()}
        records[cell_id] = summary
        for feature in record["featureCollection"]["features"]:
            p = feature.get("properties", {})
            layer = p.get("soma:layer")
            if layer not in ("roads", "buildings", "hydrography"):
                continue
            source_id = str(p.get("canonical_id") or feature.get("id") or "")
            sha = p.get("soma:geometry_sha256")
            if not source_id or not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha):
                raise SurfaceFailure("A canonical source geometry fingerprint is required")
            properties = {key: value for key, value in p.items() if not key.startswith("soma:")}
            item = source.get(source_id)
            if item is None:
                source_id = sys.intern(source_id)
                if "canonical_id" in properties:
                    properties["canonical_id"] = source_id
                item = {"id": source_id, "layer": layer, "properties": properties, "sha256": sha, "parts": []}
                source[source_id] = item
            if (item["layer"], item["properties"], item["sha256"]) != (layer, properties, sha):
                raise SurfaceFailure("Canonical source identity has contradictory tags or geometry")
            geometry = shape(p["soma:metricGeometry"])
            if not geometry.is_valid:
                raise SurfaceFailure("Prepared source geometry is invalid")
            item["parts"].append(geometry)
            if layer == "roads":
                summary["roads"].add(item["id"])
        if number % 256 == 0:
            notify("scan-vectors", completed=number, total=len(manifest["tiles"]), sources=len(source))
    del record
    notify("vectors-scanned", completed=len(records), sources=len(source))
    road_points = {source_id for source_id, item in source.items() if item["layer"] == "roads" and
                   all(part.geom_type in ("Point", "MultiPoint") for part in item["parts"])}
    road_tags = {source_id: item["properties"] for source_id, item in source.items() if item["layer"] == "roads" and source_id not in road_points}
    building_tags = {source_id: item["properties"] for source_id, item in source.items() if item["layer"] == "buildings"}
    profiles, core = profile_sources(road_tags, building_tags, baseline, node=node)
    del road_tags, building_tags
    # Validate the complete native topology, but project only axes actually
    # needed by these vector cells. No raw topology JSON survives this phase.
    needed = {source_id for source_id, item in source.items() if item["layer"] == "roads" and source_id not in road_points
              and all(part.geom_type in ("LineString", "MultiLineString") for part in item["parts"])
              and not exclusions(item["properties"], profiles["roads"][source_id])}
    topology = read_asset(manifest_path.parent, manifest.get("nativeTopology"))
    if topology.get("schema") != "soma-metropole/native-topology/1":
        raise SurfaceFailure("Native source topology is required for pre-clip road bands")
    native, native_tags, native_ids = {}, {}, set()
    for way in topology.get("ways", []):
        way_id = "osm/way/" + str(way.get("id", ""))
        if way_id in native_ids:
            raise SurfaceFailure("Duplicate native way identity")
        native_ids.add(way_id)
        coordinates, refs = way.get("coordinatesWGS84"), way.get("nodeRefs")
        if not isinstance(coordinates, list) or not isinstance(refs, list) or len(coordinates) < 2 or len(coordinates) != len(refs):
            raise SurfaceFailure("Native source node references and positions disagree")
        if any(not isinstance(q, list) or len(q) != 2 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in q)
               or not -180 <= q[0] <= 180 or not -90 <= q[1] <= 90 for q in coordinates):
            raise SurfaceFailure("Native axis coordinates must be WGS84")
        if not isinstance(way.get("tags"), dict):
            raise SurfaceFailure("Native source way tags are missing")
        if way_id in needed:
            native[way_id] = LineString([metric.transform(*q) for q in coordinates])
            native_tags[way_id] = way["tags"]
    del topology, native_ids, needed
    notify("dimensions-and-native-ready", roads=len(profiles["roads"]), buildings=len(profiles["buildings"]))
    layers = {layer: [] for layer in LAYERS}
    metadata, blockers, reasons_count = {}, [], Counter()
    for source_id, item in sorted(source.items()):
        parts = item.pop("parts")
        if item["layer"] == "buildings":
            dim = profiles["buildings"][source_id]
            if not dim["openStructure"] and dim["minHeight"] <= 0:
                blockers.extend(part for geometry in parts for part in _parts(geometry, {"Polygon"}))
            continue
        if item["layer"] == "hydrography":
            blockers.extend(part for geometry in parts for part in _parts(geometry, {"Polygon"}))
            continue
        if source_id in road_points:
            # Crossing points stay in the vector record. They are not road axes
            # and must not acquire a meaningless guessed carriageway width.
            continue
        profile = {**profiles["roads"][source_id], "geometrySHA256": item["sha256"]}
        withheld = exclusions(item["properties"], profile)
        if withheld:
            profile.update(structural=True, v69Withheld=True, v69WithheldReasons=withheld)
            reasons_count.update(withheld)
        metadata[source_id] = profile
        if withheld:
            continue
        if all(part.geom_type in ("Polygon", "MultiPolygon") for part in parts):
            # Source area fragments have already been clipped by the importer.
            # Index them separately; their union is performed only in the cell.
            layers[surface_layer(profile)].extend((source_id, part) for part in parts)
            continue
        geometry = union(parts)  # Per-object axes only, never a whole road layer.
        if geometry.geom_type in ("LineString", "MultiLineString"):
            complete = native.get(source_id)
            if complete is None or digest(mapping(complete)) != item["sha256"]:
                raise SurfaceFailure(f"Missing or contradictory full native axis: {source_id}")
            if native_tags[source_id] != {key: value for key, value in item["properties"].items() if key != "canonical_id"}:
                raise SurfaceFailure("Native and clipped source road tags disagree")
            if geometry.difference(complete.buffer(.03)).length > 1e-6:
                raise SurfaceFailure("Clipped source axis is not part of its native way")
            geometry = complete
        body, walks = road_bands(geometry, profile)
        layers[surface_layer(profile)].append((source_id, body))
        layers["walk"].append((source_id, walks))
    index = SurfaceSpatialIndex(layers, blockers)
    del source, profiles, native, native_tags, layers, blockers
    coverage = _coverage(manifest, manifest_path.parent, metric)
    if coverage is not None:
        coverage = CoverageClip(coverage)
    notify("spatial-index-ready", **index.stats)
    if file_sha256(manifest_path) != source_manifest_sha:
        raise SurfaceFailure("Source vector manifest changed during preparation")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".metropole-surfaces-", dir=output.parent) as temporary:
        stage = Path(temporary) / "surfaces"
        stage.mkdir()
        tiles, reports = [], []
        for number, (cell_id, record) in enumerate(sorted(records.items()), 1):
            bounds = record["boundsL93"]
            cell, report, intersecting_ids = index.cell(bounds, coverage)
            cell.update(contentSHA256=record["contentSHA256"], sourceSHA256=pbf_sha)
            cell_metadata = {source_id: metadata[source_id] for source_id in sorted(record["roads"] | intersecting_ids) if source_id in metadata}
            value = {"schema": CELL_SCHEMA, "version": VERSION, "cellId": cell_id, "boundsL93": bounds,
                     "contentSHA256": record["contentSHA256"], "sourcePbfSHA256": pbf_sha,
                     "sourceVectorManifestSHA256": source_manifest_sha,
                     "nativeTopologySHA256": manifest["nativeTopology"]["sha256"], "dimensionCoreSHA256": core["sha256"],
                     "cell": cell, "roadMetadata": cell_metadata, "buildings": {},
                     "heightReferences": {"status": "explicitly-absent", "provider": "IGN BD TOPO", "count": 0},
                     "policy": {"axisConstruction": "complete native source axis before buffering and cell clipping",
                                "widths": "v59 source-aware dimensions; widthSource retained per road",
                                "sidewalks": "only explicitly mapped sides",
                                "markings": "no automatic stripes or zebra geometry generated",
                                "occlusion": "source ground-level building polygons and hydrographic area polygons; courtyard holes retained"}}
            descriptor = write_asset(stage / f"{cell_id}.json.gz", value, max_tile_bytes)
            tiles.append({"cellId": cell_id, "boundsL93": bounds, "cellHash": record["contentSHA256"], "surface": descriptor})
            reports.append({"cellId": cell_id, "triangles": sum(len(t) for t in cell["surfaces"].values()),
                            "areaM2": cell["areaM2"], **report})
            if number % 256 == 0:
                notify("prepare-cells", completed=number, total=len(records), **index.stats)
        result = {"schema": MANIFEST_SCHEMA, "version": VERSION, "crs": "EPSG:2154", "units": "m",
                  "sourceVectorManifest": {"path": str(manifest_path), "sha256": source_manifest_sha},
                  "sourcePbfSHA256": pbf_sha, "nativeTopologySHA256": manifest["nativeTopology"]["sha256"],
                  "dimensionCore": core, "tiles": tiles, "coverageExplicitPartial": True, "completeMetropole": False,
                  "heightReferences": "explicitly-absent", "report": {"cells": reports, "withheldReasons": dict(reasons_count),
                    "roadWidthSources": dict(Counter(profile["widthSource"] for profile in metadata.values())),
                    "sourceRoadPointsRetainedInVectors": len(road_points),
                    "spatialPreparation": index.stats, "newElevations": 0, "inventedMarkings": 0}}
        if file_sha256(manifest_path) != source_manifest_sha:
            raise SurfaceFailure("Source vector manifest changed during preparation")
        (stage / "surface-manifest.json").write_bytes(canonical(result) + b"\n")
        stage.rename(output)
    notify("published", completed=len(records), manifest=str(output / "surface-manifest.json"), **index.stats)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--node")
    parser.add_argument("--progress", action="store_true", help="Emit bounded phase/cell progress and peak RSS as JSON lines on stderr")
    args = parser.parse_args()
    try:
        progress = (lambda event: print(json.dumps(event, ensure_ascii=False), file=sys.stderr, flush=True)) if args.progress else None
        result = prepare_surfaces(args.manifest, args.output, baseline=args.baseline, node=args.node, progress=progress)
        print(json.dumps({"status": "prepared", "tiles": len(result["tiles"]), "manifest": str(args.output / "surface-manifest.json"),
                          "widthSources": result["report"]["roadWidthSources"], "newElevations": 0}, ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Surface preparation refused: {error}\n")


if __name__ == "__main__":
    main()
