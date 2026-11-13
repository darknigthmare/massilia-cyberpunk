#!/usr/bin/env python3
"""Publish the verified, unmodified current game and its bundled geographic data."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
OUT = ROOT / "vercel-dist"
HTML = "SOMA_MASSILIA_URBAIN_v0_78.html"
VIEWER = "metropole-viewer-v78.html"
VERSION = "0.78.0"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare() -> None:
    check = [sys.executable, "-S", str(GAME / "tools/launch_cache_v78.py"), "--check"]
    ready = subprocess.run(check, cwd=ROOT, env=ENV, capture_output=True, text=True)
    if ready.returncode:
        subprocess.run([sys.executable, "-S", str(ROOT / "lancer.py"), "--prepare-only"],
                       cwd=ROOT, env=ENV, check=True)
    subprocess.run(check, cwd=ROOT, env=ENV, check=True)


def publish() -> dict:
    report = json.loads((GAME / "data/v78/BUILD_REPORT.json").read_text())
    if report.get("version") != VERSION or report.get("sha256") != sha256(GAME / HTML):
        raise ValueError("Current game differs from its verified native build report")
    viewer_report = json.loads((GAME / "data/v78/VIEWER_BUILD_REPORT.json").read_text())
    if viewer_report.get("sha256") != sha256(GAME / VIEWER):
        raise ValueError("Current viewer differs from its native build report")
    world = json.loads((GAME / "data/v69/world/manifest.json").read_text())
    if len(world.get("tiles", [])) != 168 or world.get("completeMetropole") is not False:
        raise ValueError("Expected the provided 168-cell centre, not an invented metropolitan cache")

    # Only this generated output directory is replaced. Frozen sources are never edited.
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copyfile(GAME / HTML, OUT / HTML)
    shutil.copyfile(GAME / VIEWER, OUT / VIEWER)
    # Preserve all supplied runtime data and their relative paths, including the
    # original source data. A Git clone does not contain the optional AMP cache.
    shutil.copytree(GAME / "data", OUT / "data", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    files = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file():
            files.append({"path": path.relative_to(OUT).as_posix(),
                          "bytes": path.stat().st_size, "sha256": sha256(path)})
    source_commit = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")
    if not source_commit:
        source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    release = {
        "schemaVersion": 1, "name": "Massilia Cyberpunk — SOMA//MASSILIA",
        "version": VERSION, "sourceCommit": source_commit,
        "sourceRepository": "https://github.com/darknigthmare/massilia-cyberpunk",
        "entry": HTML, "viewer": VIEWER,
        "htmlSha256": sha256(OUT / HTML), "viewerSha256": sha256(OUT / VIEWER),
        "worldManifestSha256": sha256(OUT / "data/v69/world/manifest.json"),
        "coverage": {"cells": 168, "areaKm2": 10.5, "completeMetropole": False,
                     "optionalMetropoleCacheIncluded": False},
        "runtimeBytes": sum(item["bytes"] for item in files), "files": files,
    }
    (OUT / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: release[key] for key in
                      ("version", "sourceCommit", "htmlSha256", "runtimeBytes", "coverage")}))
    return release


if __name__ == "__main__":
    prepare()
    publish()
