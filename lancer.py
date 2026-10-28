#!/usr/bin/env python3
"""Prepare the verified original release and launch SOMA//MASSILIA v0.72."""

from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
GAME = ROOT / "game"
PAYLOAD = ROOT / "payload"
CHUNK = 1024 * 1024
BUILDERS = ("build_v68.py", "build_v69.py", "build_v70.py", "build_v71.py", "build_v72.py",
            "tools/build_metropole_viewer.py", "tools/build_metropole_viewer_v70.py",
            "tools/build_metropole_viewer_v71.py", "tools/build_metropole_viewer_v72.py")


class PreparationError(Exception):
    """An incomplete or changed release must never be silently overwritten."""


def path_in(directory, relative):
    path = directory / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(directory.resolve()):
        raise PreparationError(f"Chemin de livraison invalide : {relative}")
    return path


def fingerprint(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            size += len(block)
            digest.update(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def check_file(path, expected, label):
    if not path.is_file():
        raise PreparationError(f"Fichier absent : {label}")
    if fingerprint(path) != {"bytes": expected["bytes"], "sha256": expected["sha256"]}:
        raise PreparationError(
            f"Fichier modifié ou corrompu : {label}. Aucun remplacement effectué. "
            "Conservez vos modifications ailleurs ou récupérez une copie intacte du dépôt."
        )


def check_parts(manifest):
    for item in manifest["payloads"]:
        for part in item["parts"]:
            check_file(path_in(PAYLOAD, part["file"]), part, "payload/" + part["file"])


def check_game(manifest):
    for relative, expected in manifest["original_files"].items():
        check_file(path_in(GAME, relative), expected, "game/" + relative)


def copy_bounded(source, destination, maximum):
    size = 0
    for block in iter(lambda: source.read(CHUNK), b""):
        size += len(block)
        if size > maximum:
            raise PreparationError("Le contenu décompressé dépasse la taille attendue.")
        destination.write(block)


def restore_payload(item, destination, temporary):
    destination.parent.mkdir(parents=True, exist_ok=True)
    joined = temporary / (Path(item["path"]).name + ".joined")
    with joined.open("xb") as output:
        for part in item["parts"]:
            with path_in(PAYLOAD, part["file"]).open("rb") as source:
                shutil.copyfileobj(source, output, CHUNK)
    if item["encoding"] == "gzip":
        with gzip.open(joined, "rb") as source, destination.open("xb") as output:
            copy_bounded(source, output, item["bytes"])
        joined.unlink()
    elif item["encoding"] == "raw":
        joined.rename(destination)
    else:
        raise PreparationError(f"Format de livraison inconnu : {item['encoding']}")
    check_file(destination, item, item["path"] + " (restauré)")


def install_without_overwrite(source, destination, expected):
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Same filesystem: install the fully verified file atomically, without replacement.
        os.link(source, destination)
    except FileExistsError:
        check_file(destination, expected, str(destination.relative_to(ROOT)))
    except OSError:
        # FAT/network filesystems may not support hard links. Exclusive creation still
        # guarantees that an existing user file cannot be overwritten.
        created = False
        try:
            with destination.open("xb") as output:
                created = True
                with source.open("rb") as stream:
                    shutil.copyfileobj(stream, output, CHUNK)
        except FileExistsError:
            check_file(destination, expected, str(destination.relative_to(ROOT)))
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise


def prepare(manifest):
    generated = manifest["generated"]
    large = {item["path"] for item in manifest["payloads"]} | {generated}

    # Validate all sources and any already-restored files before creating anything.
    for relative, expected in manifest["original_files"].items():
        target = path_in(GAME, relative)
        if relative not in large or target.exists() or target.is_symlink():
            check_file(target, expected, "game/" + relative)
    check_parts(manifest)

    missing = [relative for relative in large if not path_in(GAME, relative).exists()]
    if missing:
        print("Préparation du jeu complet ; aucune connexion réseau nécessaire.", flush=True)
        with tempfile.TemporaryDirectory(prefix=".massilia-prepare-", dir=ROOT) as name:
            temporary = Path(name)
            staged = temporary / "game"
            staged.mkdir()
            for item in manifest["payloads"]:
                if item["path"] in missing:
                    restore_payload(item, path_in(staged, item["path"]), temporary)

            if generated in missing:
                for relative in ("build.py", "src/v67/world-runtime.js", "baseline/v66.html"):
                    target = path_in(staged, relative)
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path_in(GAME, relative), target)
                result = subprocess.run(
                    [sys.executable, str(staged / "build.py")],
                    cwd=staged, capture_output=True, text=True, check=False,
                )
                if result.returncode:
                    raise PreparationError("La reconstruction du jeu a échoué : " + result.stderr.strip())
                check_file(path_in(staged, generated), manifest["original_files"][generated], generated)

            for relative in sorted(missing):
                install_without_overwrite(
                    path_in(staged, relative), path_in(GAME, relative),
                    manifest["original_files"][relative],
                )
    check_game(manifest)
    print("Intégrité confirmée : 27 fichiers originaux identiques, jeu prêt.", flush=True)


def main():
    if sys.version_info < (3, 11):
        raise PreparationError("Python 3.11 ou plus récent est nécessaire.")
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true", help="préparer et vérifier, sans lancer le serveur")
    mode.add_argument("--verify", action="store_true", help="vérifier la livraison déjà préparée, sans la modifier")
    parser.add_argument("--port", type=int, default=8765, help="port du serveur local (8765 par défaut)")
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir automatiquement le navigateur")
    args = parser.parse_args()
    manifest = json.loads((PAYLOAD / "manifest.json").read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("format") != 1
            or not isinstance(manifest.get("original_files"), dict)
            or len(manifest["original_files"]) != 27):
        raise PreparationError("Le manifeste de publication est invalide.")
    if args.verify:
        check_parts(manifest)
        check_game(manifest)
        print("Vérification réussie : 5 parties et 27 fichiers originaux conformes.")
        for name in BUILDERS:
            result = subprocess.call([sys.executable, str(GAME / name), "--verify"], cwd=GAME)
            if result:
                return result
        return 0
    prepare(manifest)
    if str(GAME) not in sys.path:
        sys.path.insert(0, str(GAME))
    from tools import launch_cache_v72
    if not args.prepare_only:
        cached = launch_cache_v72.try_ready(GAME)
        if cached['ready']:
            print(f"Édition 0.72 contrôlée sans reconstruction ({cached['seconds']:.2f} s).", flush=True)
            return serve(args)
    expected_sources = launch_cache_v72.source_inputs(GAME)
    for name in BUILDERS:
        result = subprocess.call([sys.executable, str(GAME / name)], cwd=GAME)
        if result:
            return result
    launch_cache_v72.record_prepared(expected_sources, GAME)
    if args.prepare_only:
        return 0
    return serve(args)


def serve(args):
    command = [sys.executable, str(GAME / "tools" / "serve_v72.py"), "--port", str(args.port)]
    if args.no_browser:
        command.append("--no-browser")
    return subprocess.call(command, cwd=GAME)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PreparationError, OSError, EOFError, ValueError, KeyError, TypeError) as error:
        print(f"Préparation impossible : {error}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
