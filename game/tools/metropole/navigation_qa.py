#!/usr/bin/env python3
"""Independently verify source-node navigation sidecars against OSM and core63.

This optional QA tool never imports the navigation generator. It checks every
asset, native segment identity, clipped interval, source permission and turn
rule, then validates every graph in one persistent process running the actual
frozen JavaScript router. Only small neighbouring graphs are merged for probes.
No historical game state or source dataset is changed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import tempfile
import time


class NavigationQAError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise NavigationQAError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def checked_asset(base, descriptor, limit=64 * 1024 * 1024):
    require(isinstance(descriptor, dict) and descriptor.get("encoding") == "gzip-json", "A checked gzip-json asset is required")
    relative = descriptor.get("path")
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), "Asset paths must be relative")
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), "Asset escapes its package")
    require(path.stat().st_size == descriptor.get("bytes") and sha256(path) == descriptor.get("sha256"), "Asset checksum or byte count differs")
    with gzip.open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit and ("decodedBytes" not in descriptor or descriptor["decodedBytes"] == len(raw)), "Decoded asset exceeds or contradicts its budget")
    return json.loads(raw)


ALLOW = {"yes", "designated", "official", "permissive"}
FALSE = {"", "no", "false", "0"}
SCOPES = {"foot": ("foot", "access"), "car": ("motorcar", "motor_vehicle", "vehicle", "access"), "bicycle": ("bicycle", "vehicle", "access")}
CAR = set("motorway motorway_link trunk trunk_link primary primary_link secondary secondary_link tertiary tertiary_link residential unclassified living_street service road track".split())
FOOT = (CAR - {"motorway", "motorway_link", "trunk", "trunk_link"}) | set("footway path steps pedestrian bridleway corridor".split())
BIKE = (CAR - {"motorway", "motorway_link"}) | {"cycleway", "path", "living_street"}
PASSABLE_BARRIERS = set("gate lift_gate swing_gate chain bollard cycle_barrier stile kissing_gate cattle_grid kerb entrance".split())
TURN_KINDS = set("no_left_turn no_right_turn no_straight_on no_u_turn no_entry no_exit only_left_turn only_right_turn only_straight_on only_u_turn".split())


def val(tags, key):
    return str(tags.get(key, "")).strip().lower()


def non_ground(tags):
    try:
        layer = float(tags.get("layer", 0))
    except (ValueError, TypeError):
        return True
    return (not math.isfinite(layer) or layer != 0 or val(tags, "highway") == "corridor"
            or any(val(tags, key) not in FALSE for key in ("bridge", "tunnel", "covered", "indoor"))
            or val(tags, "location") in {"underground", "underwater", "overground"})


def permission(tags, mode, default, direction=None):
    for scope in SCOPES[mode]:
        for key in ((scope + ":" + direction, scope) if direction else (scope,)):
            if key in tags and val(tags, key):
                return val(tags, key) in ALLOW
    return default


def conditional(tags, mode):
    keys = {"access:conditional", "barrier:conditional", "locked:conditional"}
    keys.update(scope + ":conditional" for scope in SCOPES[mode])
    keys.update(scope + ":" + direction + ":conditional" for scope in SCOPES[mode] for direction in ("forward", "backward"))
    if mode == "foot":
        keys.add("oneway:foot:conditional")
    else:
        keys.add("oneway:conditional")
        keys.update("oneway:" + scope + ":conditional" for scope in SCOPES[mode] if scope != "access")
    return any(val(tags, key) for key in keys)


def upper_mode_mask(tags, mode):
    """Maximum permissions defensible from source tags; narrower masks are safe."""
    if non_ground(tags) or val(tags, "highway") in {"construction", "proposed", "elevator"} or conditional(tags, mode):
        return 0
    defaults = {"foot": FOOT, "car": CAR, "bicycle": BIKE}
    keys = {"foot": ("oneway:foot",), "car": ("oneway:motorcar", "oneway:motor_vehicle", "oneway:vehicle", "oneway"),
            "bicycle": ("oneway:bicycle", "oneway:vehicle", "oneway")}[mode]
    direction = next((val(tags, key) for key in keys if key in tags), "")
    if direction not in {"", "yes", "true", "1", "-1", "no", "false", "0"}:
        return 0
    if not direction and mode != "foot" and (val(tags, "junction") == "roundabout" or val(tags, "highway") == "motorway"):
        direction = "yes"
    forward = permission(tags, mode, val(tags, "highway") in defaults[mode], "forward") and direction != "-1"
    backward = permission(tags, mode, val(tags, "highway") in defaults[mode], "backward") and direction not in {"yes", "true", "1"}
    return int(forward) | (int(backward) << 1)


def node_permits(tags, mode):
    if conditional(tags, mode) or non_ground(tags) or val(tags, "locked") not in FALSE:
        return False
    barrier = val(tags, "barrier")
    if barrier in FALSE:
        return permission(tags, mode, True)
    if barrier not in PASSABLE_BARRIERS or val(tags, "locked") not in FALSE or val(tags, "opening_hours") not in {"", "24/7"}:
        return False
    if mode != "foot" and barrier in {"bollard", "cycle_barrier", "stile", "kissing_gate", "kerb", "cattle_grid"}:
        specific = next((val(tags, key) for key in SCOPES[mode] if key != "access" and key in tags), "")
        if specific not in ALLOW:
            return False
    return permission(tags, mode, mode == "foot")


def restriction_contract(relations, ways):
    """Re-derive supported car turns and mandatory conservative mode removals."""
    by_via = defaultdict(list)
    removed = defaultdict(set)
    supported = {}
    for relation in relations:
        tags = relation.get("tags", {})
        if tags.get("type") != "restriction":
            continue
        members = relation.get("members", [])
        involved = {str(m.get("ref")) for m in members if m.get("type") == "way"}
        source = [str(m["ref"]) for m in members if m.get("role") == "from" and m.get("type") == "way"]
        target = [str(m["ref"]) for m in members if m.get("role") == "to" and m.get("type") == "way"]
        via = [m for m in members if m.get("role") == "via"]
        exceptions = set(re.split(r"[;,]", val(tags, "except")))
        exceptions = {entry.strip() for entry in exceptions if entry.strip()}
        kind = next((tags[key] for key in ("restriction:motorcar", "restriction:motor_vehicle", "restriction:vehicle", "restriction") if key in tags), None)
        if exceptions & {"motorcar", "motor_vehicle", "vehicle"}:
            kind = None
        closed = set()
        if tags.get("restriction:foot") or tags.get("restriction:foot:conditional"):
            closed.add("foot")
        bicycle_kind = next((tags[key] for key in ("restriction:bicycle", "restriction:vehicle", "restriction") if key in tags), None)
        if "bicycle" not in exceptions and (bicycle_kind or tags.get("restriction:bicycle:conditional")):
            closed.add("bicycle")
        if any(key in tags for key in ("restriction:conditional", "restriction:vehicle:conditional", "restriction:motorcar:conditional", "restriction:motor_vehicle:conditional", "day_on", "day_off", "hour_on", "hour_off")):
            closed.update(("car", "bicycle"))
        incidence = (len(source) == len(target) == len(via) == 1 and via[0].get("type") == "node"
                     and source[0] in ways and target[0] in ways
                     and all(str(via[0].get("ref")) in ways[w]["refs"] for w in (source[0], target[0])))
        if kind is not None and (not incidence or not isinstance(kind, str) or kind not in TURN_KINDS):
            closed.update(("car", "bicycle"))
        for way_id in involved:
            removed[way_id].update(closed)
        if kind is not None and incidence and "car" not in closed:
            normalized = kind
            if source[0] != target[0] and kind in {"no_u_turn", "only_u_turn"}:
                normalized = "no_source_transition" if kind == "no_u_turn" else "only_source_transition"
            rule = {"id": str(relation["id"]), "from": source[0], "to": target[0], "via": "n/" + str(via[0]["ref"]),
                    "kind": normalized, "sourceKind": kind, "mode": "car"}
            supported[rule["id"]] = rule
            by_via[rule["via"]].append(rule)
    return supported, by_via, removed


def line_members(geometry):
    if geometry.geom_type == "LineString":
        return [geometry] if not geometry.is_empty else []
    if hasattr(geometry, "geoms"):
        return [line for part in geometry.geoms for line in line_members(part)]
    return []


WORKER = r"""
const fs=require('node:fs'),vm=require('node:vm'),rl=require('node:readline');
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'),{filename:'verified-nav63.cjs'});
const N=globalThis.__SOMA_NAV63_CORE__;
if(!N||typeof N.validate!=='function'||typeof N.createRouter!=='function')throw Error('Missing frozen core63');
rl.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{
 try{const request=JSON.parse(line);let validated=0,probes=0;
  for(const graph of request.graphs||[]){N.validate(graph);validated++;}
  if(request.probe){N.validate(request.probe.graph);const route=N.createRouter(request.probe.graph).route(request.probe.start,request.probe.end,{mode:'foot',maxSnap:.00001,maxExpanded:10000});if(!route.ok)throw Error('Neighbour source-node route failed: '+route.reason);probes++;}
  process.stdout.write(JSON.stringify({ok:true,validated,probes})+'\n');
 }catch(error){process.stdout.write(JSON.stringify({ok:false,error:String(error.stack||error)})+'\n');}
});
"""


class RouterWorker:
    def __init__(self, script_path, deadline):
        node = shutil.which("node")
        require(node, "Node is required for independent frozen-router validation")
        self.deadline = deadline
        self.process = subprocess.Popen([node, "-e", WORKER, str(script_path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.validated = 0
        self.probes = 0

    def request(self, payload):
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "Independent navigation validation exceeded its duration budget")
        try:
            self.process.stdin.write(canonical(payload) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise NavigationQAError("Frozen-router worker stopped unexpectedly") from error
        require(self.selector.select(min(60, remaining)), "Frozen-router worker exceeded its response budget")
        line = self.process.stdout.readline()
        require(line, "Frozen-router worker exited before returning validation")
        response = json.loads(line)
        require(response.get("ok") is True, "Frozen router rejected navigation: " + str(response.get("error")))
        self.validated += response["validated"]
        self.probes += response["probes"]

    def close(self):
        self.selector.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


def merge_pair(graphs):
    """Independent two-cell merge; IDs only, no nearest-coordinate operation."""
    base = graphs[0]
    positions, metadata, hashes, edges, turns = {}, {}, {}, {}, {}
    for graph in graphs:
        require(graph["sourcePackSHA256"] == base["sourcePackSHA256"], "Neighbour graph source mismatch")
        hashes.update(graph["cellHashes"])
        for node_id, e, n in graph["nodes"]:
            if node_id in positions:
                require(math.dist(positions[node_id], (e, n)) <= 1e-6, "Neighbour identity has conflicting coordinates")
            positions[node_id] = (e, n)
        for way_id, entry in graph["ways"].items():
            require(way_id not in metadata or metadata[way_id] == entry, "Neighbour way metadata differs")
            metadata[way_id] = entry
        for edge, origin, bike in zip(graph["edges"], graph["edgeSources"], graph["bicycleMasks"]):
            a, b = graph["nodes"][edge[0]][0], graph["nodes"][edge[1]][0]
            key = (a, b, edge[2], origin["segmentIndex"], origin["t0"], origin["t1"])
            if key in edges:
                old, _, old_bike = edges[key]
                require(old[3:6] == edge[3:6] and old_bike == bike, "Neighbour source edge semantics differ")
                old[6] = sorted(set(old[6]) | set(edge[6]))
            else:
                edges[key] = ([a, b, *edge[2:]], origin, bike)
        for rule in graph["turns"]:
            turns[canonical(rule)] = rule
    require(len(positions) <= 250000 and len(edges) <= 500000, "Neighbour probe exceeds frozen router budget")
    ordered = sorted(positions)
    indexes = {node_id: index for index, node_id in enumerate(ordered)}
    values = list(edges.values())
    return {**base, "nodes": [[node_id, *positions[node_id]] for node_id in ordered], "ways": metadata, "cellHashes": hashes,
            "edges": [[indexes[edge[0]], indexes[edge[1]], *edge[2:]] for edge, _, _ in values],
            "edgeSources": [origin for _, origin, _ in values], "bicycleMasks": [bike for _, _, bike in values], "turns": list(turns.values())}


def neighbour_probe(a, b):
    shared = {row[0] for row in a["nodes"]} & {row[0] for row in b["nodes"]}
    for node_id in sorted(shared):
        incoming, outgoing = [], []
        for graph, starts, ends in ((a, incoming, None), (b, None, outgoing)):
            for edge in graph["edges"]:
                p, q = graph["nodes"][edge[0]], graph["nodes"][edge[1]]
                if starts is not None:
                    if q[0] == node_id and edge[4] & 1:
                        starts.append(p[1:])
                    if p[0] == node_id and edge[4] & 2:
                        starts.append(q[1:])
                else:
                    if p[0] == node_id and edge[4] & 1:
                        ends.append(q[1:])
                    if q[0] == node_id and edge[4] & 2:
                        ends.append(p[1:])
        for start in incoming:
            for end in outgoing:
                if math.dist(start, end) > 1e-3:
                    return {"graph": merge_pair([a, b]), "start": {"e": start[0], "n": start[1]}, "end": {"e": end[0], "n": end[1]}}
    return None


def validate_navigation(source_manifest, navigation_manifest, output_report, *, baseline=None, max_seconds=900):
    from pyproj import Transformer
    from shapely.geometry import LineString, shape
    from shapely.ops import unary_union

    source_manifest = Path(source_manifest).resolve()
    navigation_manifest = Path(navigation_manifest).resolve()
    output_report = Path(output_report).absolute()
    require(not output_report.exists(), "Refusing to replace an existing validation report")
    require(isinstance(max_seconds, (int, float)) and math.isfinite(max_seconds) and max_seconds > 0, "A positive validation duration is required")
    started = time.monotonic()
    deadline = started + max_seconds
    tool_sha = sha256(Path(__file__))

    def budget():
        require(time.monotonic() < deadline, "Independent navigation validation exceeded its duration budget")

    source_sha, nav_sha = sha256(source_manifest), sha256(navigation_manifest)
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    nav = json.loads(navigation_manifest.read_text(encoding="utf-8"))
    require(source.get("schema") == "soma-metropole/vector-tiles/1" and source.get("crs") == "EPSG:2154" and source.get("units") == "m", "Invalid source vector manifest")
    require(nav.get("schema") == "soma-metropole/navigation-tiles/1" and nav.get("crs") == "EPSG:2154" and nav.get("units") == "m", "Invalid navigation manifest")
    require(nav.get("sourceVectorManifest", {}).get("sha256") == source_sha, "Navigation source manifest SHA differs")
    require(nav.get("sourcePbfSHA256") == source.get("source", {}).get("sha256") and nav.get("nativeTopologySHA256") == source.get("nativeTopology", {}).get("sha256"), "Navigation native/PBF provenance differs")
    require(nav.get("completeMetropole") is False and nav.get("physicalMovementReady") is False and nav.get("campaignRoutingActivated") is False, "Prepared navigation must not activate movement or claim physical completeness")
    baseline = Path(baseline) if baseline is not None else Path(__file__).resolve().parents[2] / "baseline/v66.html"
    scripts = re.findall(r'<script\b[^>]*\bid="soma-v63-nav-core"[^>]*>(.*?)</script>', baseline.read_text(encoding="utf-8"), re.S)
    require(len(scripts) == 1, "Exactly one frozen source-node router script is required")
    core_sha = hashlib.sha256(scripts[0].encode("utf-8")).hexdigest()
    expected_core = {"scriptId": "soma-v63-nav-core", "version": "0.63.0", "sha256": core_sha, "baselineSHA256": sha256(baseline)}
    require(nav.get("navigationCore") == expected_core, "Navigation frozen-router fingerprint differs")
    topology = checked_asset(source_manifest.parent, source.get("nativeTopology"), 512 * 1024 * 1024)
    require(topology.get("schema") == "soma-metropole/native-topology/1" and topology.get("nodeTagsComplete") is True and isinstance(topology.get("nodeTags"), dict), "Native source node/barrier metadata is incomplete")
    projection = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    ways, native_nodes, seen_ways = {}, {}, set()
    for number, way in enumerate(topology.get("ways", [])):
        if number % 4096 == 0:
            budget()
        way_id = str(way.get("id", ""))
        require(re.fullmatch(r"[0-9]+", way_id) and way_id not in seen_ways, "Duplicate or invalid native way identity")
        seen_ways.add(way_id)
        refs, coordinates = way.get("nodeRefs"), way.get("coordinatesWGS84")
        require(isinstance(refs, list) and isinstance(coordinates, list) and len(refs) == len(coordinates) and len(refs) >= 2, "Native source nodes/coordinates disagree")
        positions = []
        for ref, point in zip(refs, coordinates):
            require(isinstance(ref, str) and re.fullmatch(r"[0-9]+", ref) and isinstance(point, list) and len(point) == 2
                    and all(isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) for value in point)
                    and -180 <= point[0] <= 180 and -90 <= point[1] <= 90, "Invalid native WGS84 position or ID")
            position = projection.transform(*point)
            require(ref not in native_nodes or math.dist(native_nodes[ref], position) <= 1e-6, "Native node has conflicting source positions")
            native_nodes[ref] = position
            positions.append(position)
        if way.get("layer") == "roads":
            require(isinstance(way.get("tags"), dict), "Native road tags missing")
            geometry_sha = hashlib.sha256(canonical({"type": "LineString", "coordinates": positions}).encode("utf-8")).hexdigest()
            ways[way_id] = {"refs": refs, "positions": positions, "tags": way["tags"], "geometrySHA256": geometry_sha}
    rules, rules_by_via, removed = restriction_contract(topology.get("relations", []), ways)
    node_tags = topology["nodeTags"]
    del topology, seen_ways
    source_tiles = {tile["cellId"]: tile for tile in source["tiles"]}
    require(len(source_tiles) == len(source["tiles"]), "Duplicate source cell ID")
    nav_tiles = {tile["cellId"]: tile for tile in nav["tiles"]}
    require(len(nav_tiles) == len(nav["tiles"]) and set(nav_tiles) == set(source_tiles), "Navigation coverage does not match source cells")
    totals = Counter()
    seen_rules, normalized_rules = set(), set()
    mode_totals = Counter()
    max_error = 0.0
    max_uncovered = 0.0
    batch, batch_bytes = [], 0
    edge_counts = {}
    with tempfile.TemporaryDirectory(prefix="massilia-navigation-qa-") as temporary:
        script_path = Path(temporary) / "nav63.cjs"
        script_path.write_text(scripts[0], encoding="utf-8")
        worker = RouterWorker(script_path, deadline)
        try:
            for number, (cell_id, tile) in enumerate(sorted(nav_tiles.items()), 1):
                budget()
                expected = source_tiles[cell_id]
                require(tile.get("boundsL93") == expected.get("boundsL93"), "Navigation cell bounds differ from vector source")
                record = checked_asset(source_manifest.parent, expected["vector"], 16 * 1024 * 1024)
                require(record.get("cellId") == cell_id and record.get("boundsL93") == expected["boundsL93"], "Vector record identity differs")
                require(record.get("sourceReceipt", {}).get("sha256") == source["source"]["sha256"], "Vector source PBF receipt differs")
                require(hashlib.sha256(canonical(record["featureCollection"]).encode("utf-8")).hexdigest() == record.get("contentSHA256"), "Source vector content SHA differs")
                graph = checked_asset(navigation_manifest.parent, tile["navigation"])
                require(graph.get("schema") == "soma/navigation-source/1" and graph.get("sourcePackSHA256") == source_sha and graph.get("sourcePbfSHA256") == source["source"]["sha256"], "Graph source provenance differs")
                require(graph.get("nativeTopologySHA256") == source["nativeTopology"]["sha256"] and graph.get("routingCoreSHA256") == core_sha, "Graph native/router provenance differs")
                require(graph.get("cellHashes") == {cell_id: record["contentSHA256"]} and tile.get("cellHash") == record["contentSHA256"], "Graph source cell hash differs")
                state = graph.get("sourceStatus", {})
                require(all(state.get(key) is True for key in ("nodeTagsComplete", "nativeNodeIdentity", "vectorConstrained")), "Graph lacks source identity guarantees")
                require(all(state.get(key) is False for key in ("completeMetropole", "physicalAccessibilityVerified", "physicalMovementReady", "campaignRoutingActivated")), "Graph incorrectly claims physical readiness or activation")
                require(len(graph["nodes"]) <= 250000 and len(graph["edges"]) <= 500000, "Graph exceeds legacy-router budgets")
                require(len(graph["edges"]) == len(graph.get("edgeSources", [])) == len(graph.get("bicycleMasks", [])), "Source edge evidence arrays differ in length")
                bounds = expected["boundsL93"]
                positions = {}
                for node_id, e, n in graph["nodes"]:
                    require(node_id not in positions and all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) for v in (e, n)), "Graph node is duplicate or nonfinite")
                    require(bounds[0] - .031 <= e <= bounds[2] + .031 and bounds[1] - .031 <= n <= bounds[3] + .031, "Graph node escapes its source cell")
                    positions[node_id] = (e, n)
                    if node_id.startswith("n/"):
                        ref = node_id[2:]
                        require(ref in native_nodes and math.dist(native_nodes[ref], (e, n)) <= 1e-6, "Graph native node moved or lost its source identity")
                        totals["nativeNodeOccurrences"] += 1
                    else:
                        require(re.fullmatch(r"clip/[0-9]+/[1-9][0-9]*/0\.[0-9]{12}", node_id), "Unknown synthetic node identity")
                        totals["clipNodeOccurrences"] += 1
                expected_node_tags = {node_id: node_tags[node_id[2:]] for node_id in positions
                                      if node_id.startswith("n/") and node_id[2:] in node_tags}
                require(graph.get("nodeTags") == expected_node_tags, "Emitted native node tags differ from source")
                visible = defaultdict(list)
                for feature in record["featureCollection"]["features"]:
                    props = feature.get("properties", {})
                    source_id = str(props.get("canonical_id") or feature.get("id", ""))
                    if props.get("soma:layer") == "roads" and source_id.startswith("osm/way/") and props.get("area") != "yes":
                        geometry = shape(props["soma:metricGeometry"])
                        members = line_members(geometry)
                        if members:
                            way_id = source_id.rsplit("/", 1)[1]
                            require(way_id in ways and props.get("soma:geometry_sha256") == ways[way_id]["geometrySHA256"], "Clipped feature native geometry fingerprint differs")
                            require({key: entry for key, entry in props.items() if not key.startswith("soma:") and key != "canonical_id"} == ways[way_id]["tags"], "Clipped feature native source tags differ")
                            visible[way_id].extend(members)
                buffers = {}
                used_nodes, edge_keys = set(), set()
                for way_id, metadata in graph["ways"].items():
                    require(way_id in ways and metadata.get("sourceTags") == ways[way_id]["tags"]
                            and metadata.get("geometrySHA256") == ways[way_id]["geometrySHA256"], "Graph way tags or native geometry SHA differ")
                for edge, origin, bike in zip(graph["edges"], graph["edgeSources"], graph["bicycleMasks"]):
                    require(isinstance(edge, list) and len(edge) >= 8 and isinstance(edge[0], int) and isinstance(edge[1], int)
                            and 0 <= edge[0] < len(graph["nodes"]) and 0 <= edge[1] < len(graph["nodes"]), "Graph edge indexes are invalid")
                    way_id, segment = str(origin.get("wayId")), origin.get("segmentIndex")
                    require(way_id == edge[2] and way_id in ways and way_id in visible and isinstance(segment, int) and not isinstance(segment, bool)
                            and 1 <= segment < len(ways[way_id]["refs"]) and edge[7] == segment, "Edge lost its original native way/segment")
                    t0, t1 = origin.get("t0"), origin.get("t1")
                    require(all(isinstance(t, (float, int)) and not isinstance(t, bool) and math.isfinite(t) for t in (t0, t1)) and 0 <= t0 < t1 <= 1, "Invalid source clipping interval")
                    a, b = ways[way_id]["positions"][segment - 1:segment + 1]
                    edge_key = (way_id, segment, t0, t1)
                    require(edge_key not in edge_keys, "A source segment interval is duplicated inside a graph")
                    edge_keys.add(edge_key)
                    used_nodes.update((edge[0], edge[1]))
                    for index, t, native_flag, native_ref in ((edge[0], t0, origin.get("startNative"), ways[way_id]["refs"][segment - 1]),
                                                            (edge[1], t1, origin.get("endNative"), ways[way_id]["refs"][segment])):
                        node_id, e, n = graph["nodes"][index]
                        reference = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                        error = math.dist((e, n), reference)
                        max_error = max(max_error, error)
                        require(error <= 1e-6, "Clipped node is not an interpolation of its source segment")
                        require(isinstance(native_flag, bool) and native_flag == node_id.startswith("n/"), "Native endpoint evidence differs")
                        require(native_flag == (t in (0, 1)), "A native segment endpoint was replaced with a synthetic identity")
                        expected_id = "n/" + native_ref if native_flag else f"clip/{way_id}/{segment}/{t:.12f}"
                        require(node_id == expected_id and (not native_flag or t in (0, 1)), "Endpoint ID/parameter provenance differs")
                    p, q = graph["nodes"][edge[0]][1:], graph["nodes"][edge[1]][1:]
                    require(math.isfinite(edge[3]) and edge[3] > 0 and abs(math.dist(p, q) - edge[3]) <= 1e-6, "Edge source distance differs")
                    require(edge[6] == [cell_id] and edge[5] == int(ways[way_id]["tags"].get("highway") == "steps"), "Edge cell/staircase evidence differs")
                    if way_id not in buffers:
                        buffers[way_id] = unary_union(visible[way_id]).buffer(.030001)
                    uncovered = LineString([p, q]).difference(buffers[way_id]).length
                    max_uncovered = max(max_uncovered, uncovered)
                    require(uncovered <= 1e-6, "Edge invents a segment absent from its clipped source geometry")
                    require(isinstance(edge[4], int) and not isinstance(edge[4], bool) and 1 <= edge[4] <= 15 and isinstance(bike, int) and not isinstance(bike, bool) and 0 <= bike <= 3, "Invalid source mode bits")
                    for mode, mask in (("foot", edge[4] & 3), ("car", (edge[4] >> 2) & 3), ("bicycle", bike)):
                        permitted = upper_mode_mask(ways[way_id]["tags"], mode)
                        if mode in removed.get(way_id, ()) or any(not node_permits(node_tags.get(ref, {}), mode) for ref in ways[way_id]["refs"][segment - 1:segment + 1]):
                            permitted = 0
                        require(mask & ~permitted == 0, "Edge authorizes a mode/direction denied by source access, structure, barrier or restriction")
                        if mask:
                            mode_totals[mode + "EdgeOccurrences"] += 1
                    totals["edges"] += 1
                require(used_nodes == set(range(len(graph["nodes"]))), "A graph contains an unreferenced or unsupported node")
                expected_turns = {rule["id"]: rule for node_id in positions for rule in rules_by_via.get(node_id, ())}
                actual_turns = {}
                for rule in graph["turns"]:
                    require(rule.get("id") not in actual_turns and rule.get("id") in expected_turns and rule == expected_turns[rule["id"]], "Turn restriction is duplicated, changed or not source-backed")
                    actual_turns[rule["id"]] = rule
                    seen_rules.add(rule["id"])
                    if rule["kind"] != rule["sourceKind"]:
                        normalized_rules.add(rule["id"])
                require(set(actual_turns) == set(expected_turns), "A supported source restriction was silently omitted")
                totals["nodes"] += len(graph["nodes"])
                totals["turnOccurrences"] += len(graph["turns"])
                totals["cells"] += 1
                edge_counts[cell_id] = len(graph["edges"])
                serialized = canonical(graph)
                if batch and (len(batch) >= 64 or batch_bytes + len(serialized.encode("utf-8")) > 4 * 1024 * 1024):
                    worker.request({"graphs": batch})
                    batch, batch_bytes = [], 0
                batch.append(graph)
                batch_bytes += len(serialized.encode("utf-8"))
                if number % 4096 == 0:
                    print(canonical({"phase": "validate-navigation", "completed": number, "total": len(nav_tiles), "elapsedSeconds": round(time.monotonic() - started, 2)}), flush=True)
            if batch:
                worker.request({"graphs": batch})
            require(worker.validated == len(nav_tiles), "Frozen router did not validate every graph")
            grid = {(tile.get("gridX"), tile.get("gridY")): tile["cellId"] for tile in source["tiles"] if isinstance(tile.get("gridX"), int) and isinstance(tile.get("gridY"), int)}
            samples = 0
            pairs = [(cell_id, grid[neighbour]) for (x, y), cell_id in grid.items() for neighbour in ((x + 1, y), (x, y + 1))
                     if neighbour in grid and edge_counts.get(cell_id) and edge_counts.get(grid[neighbour])]
            pairs.sort(key=lambda pair: (-min(edge_counts[pair[0]], edge_counts[pair[1]]), pair))
            for cell_id, neighbour in pairs[:128]:
                if samples >= 16:
                    break
                budget()
                a = checked_asset(navigation_manifest.parent, nav_tiles[cell_id]["navigation"])
                b = checked_asset(navigation_manifest.parent, nav_tiles[neighbour]["navigation"])
                probe = neighbour_probe(a, b)
                if probe:
                    worker.request({"probe": probe})
                    samples += 1
            require(sha256(source_manifest) == source_sha and sha256(navigation_manifest) == nav_sha, "An input manifest changed during independent validation")
            require(sha256(Path(__file__)) == tool_sha, "The independent validation tool changed during validation")
            import resource
            result = {"schema": "soma-metropole/navigation-validation/1", "status": "passed", "sourceVectorManifestSHA256": source_sha,
                      "navigationManifestSHA256": nav_sha, "sourcePbfSHA256": source["source"]["sha256"],
                      "nativeTopologySHA256": source["nativeTopology"]["sha256"], "navigationCore": expected_core,
                      "routingCoreSHA256": expected_core["sha256"], "baselineSHA256": expected_core["baselineSHA256"],
                      "cellsValidated": len(nav_tiles), "cellSetSHA256": hashlib.sha256(canonical(sorted(nav_tiles)).encode("utf-8")).hexdigest(),
                      "toolSHA256": tool_sha,
                      "checks": {**dict(totals), **dict(mode_totals), "sourceAssetChecks": len(nav_tiles), "navigationAssetChecks": len(nav_tiles),
                                 "actualFrozenRouterValidatedGraphs": worker.validated, "neighbourRoutingProbes": worker.probes,
                                 "uniqueRestrictionsSeen": len(seen_rules), "normalizedDistinctWayUTurnRestrictionsSeen": len(normalized_rules),
                                 "maximumSourceInterpolationErrorM": max_error, "maximumUncoveredSourceEdgeLengthM": max_uncovered},
                      "sourceUnchanged": True, "navigationUnchanged": True, "physicalMovementReady": False, "campaignRoutingActivated": False,
                      "physicalAccessibilityVerified": False, "completeMetropole": False,
                      "elapsedSeconds": round(time.monotonic() - started, 3), "peakRssMiB": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
            result["proofSHA256"] = hashlib.sha256(canonical(result).encode("utf-8")).hexdigest()
        finally:
            worker.close()
    output_report.parent.mkdir(parents=True, exist_ok=True)
    with output_report.open("x", encoding="utf-8") as stream:
        stream.write(canonical(result) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--navigation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--max-seconds", type=float, default=900)
    args = parser.parse_args()
    try:
        result = validate_navigation(args.source, args.navigation, args.output, baseline=args.baseline, max_seconds=args.max_seconds)
        print(canonical(result))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Independent navigation validation refused: {error}\n")


if __name__ == "__main__":
    main()
