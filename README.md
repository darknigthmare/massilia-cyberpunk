# Massilia Cyberpunk — SOMA//MASSILIA v0.67

**« Quartiers vivants » — jeu complet, sources et données incluses.**

Ce dépôt contient tous les éléments de la livraison originale v0.67 : le module de jeu, les données OSM/IGN, la base v0.66, les scripts, les tests et les documents de livraison. Les trois fichiers volumineux sont restaurés automatiquement à partir des éléments inclus. La préparation ne télécharge rien et n'utilise que la bibliothèque standard de Python.

## Jouer

1. Récupérez toute la branche du dépôt, par clonage ou avec **Code → Download ZIP**, puis extrayez complètement l'archive.
2. Installez **Python 3.11 ou plus récent** si nécessaire.
3. Sous Windows, lancez `LANCER_JEU.cmd`. Sous Linux/macOS, exécutez à la racine du dépôt :

   ```sh
   python3 lancer.py
   ```

Le premier lancement reconstitue les fichiers volumineux, contrôle leurs empreintes SHA256 et ouvre le jeu dans votre navigateur. Le serveur écoute uniquement sur `127.0.0.1:8765`. Fermez le terminal ou utilisez `Ctrl+C` pour l'arrêter. Prévoyez environ 350 Mo d'espace libre pour la préparation temporaire, en plus du dépôt téléchargé.

Pour préparer puis vérifier le jeu sans démarrer le serveur :

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
```

Sous Windows, remplacez `python3` par `python`. Les options `--no-browser` et `--port 8766` permettent respectivement de garder le navigateur fermé et de choisir un autre port.

## Contenu et intégrité

| Emplacement | Contenu |
|---|---|
| `game/` | Les 24 petits fichiers originaux, inchangés : code, données, tests, scripts et documentation. Après préparation, les 27 fichiers originaux s'y trouvent. |
| `payload/` | Deux parties gzip de la base HTML v0.66, trois parties du fichier OSM PBF et le manifeste SHA256 de publication. Chaque partie fait au maximum 20 MiB. |
| `lancer.py` | Préparation, vérification et lancement avec Python uniquement. |

Le découpage permet la publication par l'interface web de GitHub. Il ne retire aucune donnée du jeu. Le HTML courant est reconstruit par le `game/build.py` d'origine, à partir de la base v0.66 et du module `game/src/v67/world-runtime.js`, puis comparé à l'empreinte de la livraison originale :

```text
SOMA_MASSILIA_URBAIN_v0_67.html
51 742 676 octets
SHA256 f4f30ee5d08c9596398a5762c79287c7e67ccebf0796150f52d552156331294f
```

Le lanceur contrôle les parties et les fichiers restaurés. Il s'arrête si un fichier est absent, tronqué, corrompu ou modifié ; il ne remplace pas un fichier existant différent. Le manifeste de livraison original est conservé sans modification dans `game/MANIFEST_v67.json`.

## Développer ou reconstruire

Préparez d'abord la livraison originale avec `python3 lancer.py --prepare-only`. Vous pouvez ensuite modifier les sources dans `game/` et utiliser les commandes d'origine :

```sh
python3 game/build.py
node --check game/src/v67/world-runtime.js
node game/tests/v67/core.test.cjs
python3 game/tools/serve_game.py
```

`build.py` reconstruit le HTML courant et vérifie l'intégrité de la base v0.66 gelée. Le serveur d'origine lance votre version modifiée. Le lanceur racine et `--verify` servent à contrôler la **livraison originale** : ils refuseront donc des fichiers modifiés. Pour vérifier une nouvelle version, conservez vos changements et utilisez un manifeste propre à cette version.

## Version et validation

La v0.67 ajoute des ambiances contextuelles par quartier, des conversations locales optionnelles, un état du quartier enrichi, une régulation du trafic et des modes de densité visuelle. La carte, le relief, les POI, la navigation et les fonctionnalités de la v0.66 sont conservés. Voir `game/README_v67.md` et les rapports d'origine pour le détail.

La préparation et la reconstruction sont vérifiées par les empreintes des 27 fichiers ; les tests ciblés du module comportent 10 contrôles. Ces vérifications ne constituent pas une certification complète des campagnes ni du rendu WebGL/GPU sur toutes les machines.
