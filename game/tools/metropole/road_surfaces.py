"""Withhold unsupported indoor/covered road surfaces without changing source data.

Generation needs Shapely 2.1.2. Applying the generated patch during an ordinary
game build uses only Python's standard library. The patch is a subtraction from
existing v59 surface triangles, never a new road, a new elevation or a graph edit.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re

SCHEMA = "soma-massilia/road-surface-correction/1"
FIDELITY_ID = "soma-v59-fidelity-data"
PACK_ID = "soma-v53-embedded-pack"
LAYERS = ("road", "unsealed", "paved", "foot", "walk", "mark")
AREA_EPSILON = 1e-8
VERSION = "0.69.0"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def object_digest(value):
    return digest(canonical(value))


def _positive(value):
    if value is False or value == 0:
        return False
    return str(value if value is not None else "").strip().lower() not in ("", "no", "false", "0")


def withheld_reasons(properties):
    """A DTM supplies neither indoor access levels nor bridge/tunnel decks."""
    properties = properties or {}
    reasons = []
    layer = str(properties.get("layer") or "0").strip()
    try:
        number = float(layer or "0")
        if not math.isfinite(number) or number != 0:
            reasons.append("nonzero-or-unknown-layer")
    except (ValueError, TypeError):
        reasons.append("nonzero-or-unknown-layer")
    for field in ("bridge", "tunnel", "covered", "indoor"):
        if _positive(properties.get(field)):
            reasons.append(field)
    return reasons


def _script_pattern(script_id):
    return re.compile(r'(<script\b[^>]*\bid="' + re.escape(script_id) + r'"[^>]*>)(.*?)(</script>)', re.S)


def _embedded(html, script_id, maximum=256 * 1024 * 1024):
    matches = list(_script_pattern(script_id).finditer(html))
    if len(matches) != 1:
        raise ValueError(f"Embedded source missing or duplicated: {script_id}")
    match = matches[0]
    attributes = dict(re.findall(r'([\w-]+)="([^\"]*)"', match[1]))
    if attributes.get("data-encoding") != "gzip-base64":
        raise ValueError(f"Unsupported embedded encoding: {script_id}")
    try:
        size = int(attributes["data-bytes"])
        expected = attributes["data-sha256"]
    except (KeyError, ValueError) as error:
        raise ValueError(f"Missing source checksum or size: {script_id}") from error
    if not 2 <= size <= maximum or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError(f"Invalid embedded source contract: {script_id}")
    compressed = base64.b64decode("".join(match[2].split()), validate=True)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(size + 1)
        if len(raw) != size or stream.read(1):
            raise ValueError(f"Embedded source size mismatch: {script_id}")
    if digest(raw) != expected:
        raise ValueError(f"Embedded source checksum mismatch: {script_id}")
    return json.loads(raw), {"sha256": expected, "bytes": size}, match


def _encode_blob(value):
    raw = canonical(value)
    # GzipFile avoids the platform-specific gzip.compress(mtime=0) OS header
    # used by some supported Python versions.
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0, compresslevel=9) as stream:
        stream.write(raw)
    return raw, base64.b64encode(output.getvalue()).decode("ascii")


def _shapely():
    try:
        import shapely
        from shapely.geometry import Polygon, box, shape
        from shapely.affinity import affine_transform
        from shapely.ops import unary_union
    except ImportError as error:
        raise RuntimeError("Generation requires the geodata environment with Shapely 2.1.2.") from error
    if not hasattr(shapely, "constrained_delaunay_triangles"):
        raise RuntimeError("Shapely constrained triangulation is required; use Shapely 2.1.2.")
    return shapely, Polygon, box, shape, affine_transform, unary_union


def _road_corridor(geometry, profile):
    """Derived clearance mask using the SAME v59 road/sidewalk widths.

    End caps deliberately cover the source endpoint envelope; the result is
    intersected with existing surface triangles and can never add paved area.
    Explicit left/right sidewalks use Lambert-93 northing, not inverted local Z.
    """
    _, _, _, _, _, union = _shapely()
    if geometry.is_empty:
        return geometry
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return geometry
    if geometry.geom_type not in ("LineString", "MultiLineString"):
        raise ValueError(f"Unsupported road mask geometry: {geometry.geom_type}")
    width = profile.get("width")
    if not isinstance(width, (int, float)) or isinstance(width, bool) or not math.isfinite(width) or not 0 < width <= 100:
        raise ValueError("Invalid source road width")
    lines = [geometry] if geometry.geom_type == "LineString" else list(geometry.geoms)
    output = []
    side = profile.get("sidewalk") or {}
    for line in lines:
        output.append(line.buffer(width / 2, cap_style="square", join_style="mitre"))
        for name, sign in (("left", 1), ("right", -1)):
            if not side.get(name):
                continue
            sw = side.get(name + "Width")
            if not isinstance(sw, (int, float)) or isinstance(sw, bool) or not math.isfinite(sw) or not 0 < sw <= 8:
                raise ValueError("Invalid source sidewalk width")
            # Buffering the whole half-corridor includes the existing carriageway
            # too; union below makes it a single support mask.
            output.append(line.buffer(sign * (width / 2 + sw), single_sided=True, join_style="mitre"))
    return union(output)


def _triangle_polygon(triangle):
    _, Polygon, _, _, _, _ = _shapely()
    if not isinstance(triangle, list) or len(triangle) != 3:
        raise ValueError("Invalid original surface triangle")
    if any(not isinstance(point, list) or len(point) != 2 or
           any(not isinstance(number, (int, float)) or not math.isfinite(number) for number in point)
           for point in triangle):
        raise ValueError("Non-finite original surface triangle")
    polygon = Polygon(triangle)
    if not polygon.is_valid:
        raise ValueError("Invalid original surface triangle geometry")
    return polygon


def _triangles(geometry):
    shapely, _, _, _, _, union = _shapely()
    if geometry.is_empty:
        return []
    if geometry.geom_type == "GeometryCollection":
        pieces = [part for part in geometry.geoms if part.geom_type in ("Polygon", "MultiPolygon") and part.area > AREA_EPSILON]
        geometry = union(pieces)
        if geometry.is_empty:
            return []
    if geometry.geom_type not in ("Polygon", "MultiPolygon"):
        if geometry.area <= AREA_EPSILON:
            return []
        raise ValueError("Non-polygonal corrected road surface")
    result = []
    for polygon in shapely.constrained_delaunay_triangles(geometry).geoms:
        if polygon.area <= AREA_EPSILON:
            continue
        points = [list(point) for point in list(polygon.exterior.coords)[:-1]]
        if len(points) != 3:
            raise ValueError("Constrained triangulation returned a non-triangle")
        start = min(range(3), key=lambda i: points[i])
        points = points[start:] + points[:start]
        result.append(points)
    result.sort()
    covered = union([_triangle_polygon(triangle) for triangle in result])
    tolerance = max(1e-6, geometry.area * 1e-9)
    if covered.symmetric_difference(geometry).area > tolerance:
        raise ValueError("Triangulation changed a boundary or filled a courtyard")
    return result


def correct_cell(cell, bounds_l93, withdrawal, protected):
    """Subtract unsupported-only area from one cell; preserve every valid overlap.

    Geometry arguments are Lambert-93 Shapely polygons. Returned triangles remain
    in the original local east/south coordinate system. Uncut triangles retain
    their exact original coordinates and order.
    """
    _, _, box, _, transform, union = _shapely()
    if len(bounds_l93) != 4 or not all(math.isfinite(number) for number in bounds_l93):
        raise ValueError("Invalid cell bounds")
    ce = (bounds_l93[0] + bounds_l93[2]) / 2
    cn = (bounds_l93[1] + bounds_l93[3]) / 2
    frame = [1, 0, 0, -1, -ce, cn]
    local_withdrawal = transform(withdrawal.intersection(box(*bounds_l93)), frame)
    local_protected = transform(protected.intersection(withdrawal).intersection(box(*bounds_l93)), frame)
    removal = local_withdrawal.difference(local_protected)
    output = copy.deepcopy(cell)
    report = {"removedLayerAreaM2": {}, "validOverlapLostM2": 0.0,
              "validOverlapPreservedM2": 0.0, "changedTriangles": 0,
              "beforeTriangles": 0, "afterTriangles": 0}
    removed_pieces = []
    for layer, triangles in cell.get("surfaces", {}).items():
        if layer not in LAYERS:
            raise ValueError(f"Unknown surface layer: {layer}")
        before_polygons = [_triangle_polygon(triangle) for triangle in triangles]
        before = union(before_polygons)
        new_triangles = []
        for triangle, polygon in zip(triangles, before_polygons):
            cut = polygon.intersection(removal)
            if cut.area <= AREA_EPSILON:
                new_triangles.append(copy.deepcopy(triangle))
            else:
                report["changedTriangles"] += 1
                new_triangles.extend(_triangles(polygon.difference(removal)))
        after = union([_triangle_polygon(triangle) for triangle in new_triangles])
        removed = before.difference(after)
        added = after.difference(before).area
        valid = before.intersection(local_protected)
        lost = valid.difference(after).area
        if added > 1e-6 or lost > 1e-6:
            raise ValueError("Correction added pavement or removed a supported crossing")
        report["removedLayerAreaM2"][layer] = removed.area
        report["validOverlapLostM2"] = max(report["validOverlapLostM2"], lost)
        report["validOverlapPreservedM2"] += valid.area
        report["beforeTriangles"] += len(triangles)
        report["afterTriangles"] += len(new_triangles)
        removed_pieces.append(removed)
        output["surfaces"][layer] = new_triangles
        if layer in output.get("areaM2", {}):
            output["areaM2"][layer] = after.area
    report["removedFootprintAreaM2"] = union(removed_pieces).area
    report["removedLayerAreaTotalM2"] = sum(report["removedLayerAreaM2"].values())
    return output, report


def _summary(patch):
    report = patch["report"]
    return {"version": VERSION,
            "withheldSourceWays": len(patch["roadMetadata"]),
            "correctedSurfaceCells": len(patch["cells"]),
            "removedFootprintAreaM2": report["removedFootprintAreaM2"],
            "removedLayerAreaM2": report["removedLayerAreaM2"],
            "maximumValidOverlapLostM2": report["maximumValidOverlapLostM2"],
            "originalSurfaceTriangles": report["beforeSurfaceTriangles"],
            "sourceGeometryChanged": False, "navigationGraphChanged": False,
            "newElevations": 0, "stairs": report["stairs"]}


def _apply_data(data, patch):
    output = copy.deepcopy(data)
    for cell_id, change in patch["cells"].items():
        before = output.get("cells", {}).get(cell_id)
        if before is None or object_digest(before) != change["beforeSHA256"]:
            raise ValueError(f"Road correction targets a different cell: {cell_id}")
        after = change["replacement"]
        if object_digest(after) != change["afterSHA256"]:
            raise ValueError(f"Corrupt corrected cell: {cell_id}")
        if {k: v for k, v in before.items() if k not in ("surfaces", "areaM2")} != {
                k: v for k, v in after.items() if k not in ("surfaces", "areaM2")}:
            raise ValueError("A surface correction cannot change source cell identity")
        output["cells"][cell_id] = copy.deepcopy(after)
    for source_id, change in patch["roadMetadata"].items():
        before = output.get("roadMetadata", {}).get(source_id)
        if before is None or object_digest(before) != change["beforeSHA256"]:
            raise ValueError(f"Road correction targets a different source profile: {source_id}")
        after = change["replacement"]
        if object_digest(after) != change["afterSHA256"]:
            raise ValueError(f"Corrupt corrected road profile: {source_id}")
        changed_fields = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
        if not changed_fields <= {"structural", "v69Withheld", "v69WithheldReasons"} or not after.get("structural"):
            raise ValueError("Correction changed a source road dimension or identity")
        output["roadMetadata"][source_id] = copy.deepcopy(after)
    stats = output.setdefault("stats", {})
    stats["surfaceTriangles"] = sum(len(layer) for cell in output["cells"].values() for layer in cell["surfaces"].values())
    stats["unsupportedVerticalRoads"] = sum(bool(row.get("structural")) for row in output["roadMetadata"].values())
    stats["v69SurfaceCorrection"] = _summary(patch)
    return output


def _validate_patch(patch):
    if not isinstance(patch, dict) or patch.get("schema") != SCHEMA:
        raise ValueError("Unsupported road correction schema")
    body = copy.deepcopy(patch)
    integrity = body.pop("integrity", None)
    if not isinstance(integrity, dict) or object_digest(body) != integrity.get("sha256"):
        raise ValueError("Road correction checksum mismatch")


def apply_to_html(html, patch):
    """Apply a verified generated patch using the standard library only."""
    if not isinstance(html, str):
        raise TypeError("HTML must be text")
    _validate_patch(patch)
    data, contract, match = _embedded(html, FIDELITY_ID, maximum=64 * 1024 * 1024)
    # The canonical geographic pack is not rewritten. Check its byte contract
    # without needing Shapely or another expensive JSON parse during each build.
    pack_matches = list(_script_pattern(PACK_ID).finditer(html))
    if len(pack_matches) != 1:
        raise ValueError("Source geographic pack missing or duplicated")
    pack_attrs = dict(re.findall(r'([\w-]+)="([^\"]*)"', pack_matches[0][1]))
    if pack_attrs.get("data-sha256") != patch["sources"]["geographicPack"]["sha256"]:
        raise ValueError("Road correction was prepared for different geographic sources")
    if contract["sha256"] == patch["targetDataSHA256"]:
        return html
    if contract != patch["sources"]["fidelityData"]:
        raise ValueError("Road correction was prepared for different fidelity data")
    corrected = _apply_data(data, patch)
    raw, encoded = _encode_blob(corrected)
    if digest(raw) != patch["targetDataSHA256"]:
        raise ValueError("Corrected road data does not match its generated checksum")
    opening = re.sub(r'\bdata-bytes="[^"]*"', f'data-bytes="{len(raw)}"', match[1])
    opening = re.sub(r'\bdata-sha256="[^"]*"', f'data-sha256="{digest(raw)}"', opening)
    return html[:match.start()] + opening + encoded + match[3] + html[match.end():]


def generate(baseline_path, outpath):
    """Generate the targeted subtraction patch from verified frozen data."""
    shapely, _, box, shape, _, union = _shapely()
    baseline_path = Path(baseline_path)
    html_bytes = baseline_path.read_bytes()
    html = html_bytes.decode("utf-8")
    pack, pack_contract, _ = _embedded(html, PACK_ID)
    data, data_contract, _ = _embedded(html, FIDELITY_ID, maximum=64 * 1024 * 1024)
    if pack.get("schema") != "soma-massilia/geodata-pack/4" or data.get("schema") != "soma-massilia/fidelity-overlay/1":
        raise ValueError("Unexpected source pack schema")
    records = pack["records"]
    by_cell = {record["cellId"]: record for record in records}
    ways = {}
    source_cells = set()
    stairs = {}
    for record in records:
        cell = data["cells"].get(record["cellId"])
        if cell is None or cell["contentSHA256"] != record["contentSHA256"] or cell["sourceSHA256"] != record["sourceReceipt"]["sha256"]:
            raise ValueError("Fidelity surface data and source cell do not match")
        for feature in record["featureCollection"]["features"]:
            properties = feature.get("properties", {})
            if properties.get("soma:layer") != "roads":
                continue
            source_id = str(properties.get("canonical_id") or feature["id"])
            profile = data["roadMetadata"].get(source_id)
            if not profile or profile.get("geometrySHA256") != properties.get("soma:geometry_sha256"):
                raise ValueError(f"Unmatched source road profile: {source_id}")
            metric = properties.get("soma:metricGeometry")
            if not metric:
                raise ValueError("Source road lacks prepared metric geometry")
            geometry = shape(metric)
            if not geometry.is_valid:
                raise ValueError(f"Invalid prepared source road geometry: {source_id}")
            entry = ways.setdefault(source_id, {"properties": properties, "profile": profile, "geometries": [], "cells": set()})
            if entry["profile"] != profile:
                raise ValueError("Contradictory canonical road profile")
            entry["geometries"].append(geometry)
            entry["cells"].add(record["cellId"])
            if properties.get("highway") == "steps":
                stairs[source_id] = properties
    unsupported = {source_id: entry for source_id, entry in ways.items()
                   if withheld_reasons(entry["properties"]) and not entry["profile"].get("structural")}
    withdrawal_pieces = []
    for entry in unsupported.values():
        source_cells.update(entry["cells"])
        withdrawal_pieces.extend(_road_corridor(geometry, entry["profile"]) for geometry in entry["geometries"])
    withdrawal = union(withdrawal_pieces)
    support_pieces = []
    for entry in ways.values():
        if entry["profile"].get("structural") or withheld_reasons(entry["properties"]):
            continue
        for geometry in entry["geometries"]:
            # Widths and declared sidewalks stay the existing v59 estimates;
            # no measured-width or survey-precision claim is introduced here.
            corridor = _road_corridor(geometry, entry["profile"])
            if corridor.intersects(withdrawal):
                support_pieces.append(corridor.intersection(withdrawal))
    protected = union(support_pieces)
    stairs_report = {"uniqueWays": len(stairs),
                     "withStepCount": sum("step_count" in props for props in stairs.values()),
                     "withIncline": sum("incline" in props for props in stairs.values()),
                     "withExplicitElevation": sum(any(key in props for key in ("ele", "height", "step_height", "step:height")) for props in stairs.values()),
                     "newStepVolumes": 0,
                     "status": "unresolved-no-surveyed-step-elevations; mapped axes and IGN terrain preserved"}
    patch = {"schema": SCHEMA, "version": VERSION,
             "sources": {"baselineSHA256": digest(html_bytes), "geographicPack": pack_contract,
                         "fidelityData": data_contract,
                         "sourcePbfSHA256": pack["sourceReceipt"]["sha256"]},
             "generator": {"shapely": shapely.__version__, "geos": shapely.geos_version_string,
                           "operation": "existing surface minus unsupported corridor except supported surface overlap",
                           "widths": "unchanged v59 OSM/lanes/class estimates; square endpoint envelope; explicit sidewalks"},
             "roadMetadata": {}, "cells": {},
             "report": {"sourceAffectedCells": sorted(source_cells), "removedFootprintAreaM2": 0.0,
                        "removedLayerAreaM2": {layer: 0.0 for layer in LAYERS},
                        "maximumValidOverlapLostM2": 0.0, "validOverlapPreservedM2": 0.0,
                        "changedTriangles": 0, "stairs": stairs_report,
                        "beforeSurfaceTriangles": sum(len(layer) for cell in data["cells"].values() for layer in cell["surfaces"].values())}}
    for source_id, entry in sorted(unsupported.items()):
        before = entry["profile"]
        after = {**before, "structural": True, "v69Withheld": True,
                 "v69WithheldReasons": withheld_reasons(entry["properties"])}
        patch["roadMetadata"][source_id] = {"beforeSHA256": object_digest(before),
                                            "afterSHA256": object_digest(after), "replacement": after}
    for cell_id, cell in sorted(data["cells"].items()):
        bounds = by_cell[cell_id]["boundsL93"]
        if not withdrawal.intersects(box(*bounds)):
            continue
        after, report = correct_cell(cell, bounds, withdrawal, protected)
        if report["changedTriangles"] == 0:
            continue
        patch["cells"][cell_id] = {"beforeSHA256": object_digest(cell), "afterSHA256": object_digest(after),
                                   "replacement": after, "report": report}
        total = patch["report"]
        total["removedFootprintAreaM2"] += report["removedFootprintAreaM2"]
        total["validOverlapPreservedM2"] += report["validOverlapPreservedM2"]
        total["maximumValidOverlapLostM2"] = max(total["maximumValidOverlapLostM2"], report["validOverlapLostM2"])
        total["changedTriangles"] += report["changedTriangles"]
        for layer, area in report["removedLayerAreaM2"].items():
            total["removedLayerAreaM2"][layer] += area
    patch["report"]["afterSurfaceTriangles"] = patch["report"]["beforeSurfaceTriangles"] + sum(
        change["report"]["afterTriangles"] - change["report"]["beforeTriangles"] for change in patch["cells"].values())
    corrected = _apply_data(data, patch)
    patch["targetDataSHA256"] = object_digest(corrected)
    patch["integrity"] = {"sha256": object_digest(patch)}
    _validate_patch(patch)
    outpath = Path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_bytes(canonical(patch) + b"\n")
    return patch


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=root / "baseline/v66.html")
    parser.add_argument("--output", type=Path, default=root / "data/v69/road-surfaces.json")
    args = parser.parse_args()
    patch = generate(args.baseline, args.output)
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size,
                      "withheldWays": len(patch["roadMetadata"]), "changedCells": len(patch["cells"]),
                      **patch["report"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
