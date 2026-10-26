# Massilia Cyberpunk — SOMA//MASSILIA v0.69

**Marseille augmentée** poursuit la reconstruction de la ville dans l’ambiance cyberpunk du projet : architecture méditerranéenne, fenêtres éclairées et accents cyan, magenta et ambre.

La campagne embarquée couvre **168 cellules de 250 m, soit 10,5 km² du centre de Marseille**. Le nouveau survol couvre les **92 communes de la métropole Aix-Marseille-Provence**, avec **52 020 secteurs de relief IGN à 5 m**, les objets OSM et **299 391 références IGN de hauteur à l’égout**. Le cache métropolitain complet est installé dans cet environnement cloud ; il reste hors Git. Une copie source seule utilise explicitement le centre partiel jusqu’à préparation des données. Les façades, toitures et dimensions encore inconnues restent interprétées : la restitution architecturale complète à 1:1 n’est pas atteinte.

## Jouer

Utilisez une copie complète de cette version, avec `game/`, `payload/` et le lanceur à la racine. Python **3.11 ou plus récent** et un navigateur compatible **WebGL 2** suffisent ; aucun outil GIS ou Node.js n’est nécessaire pour jouer.

- Windows : lancez **`LANCER_JEU.cmd` à la racine du dépôt**.
- Linux/macOS : depuis la racine, exécutez `python3 lancer.py`.

Le premier lancement restaure les fichiers originaux, vérifie leurs empreintes, reconstruit les éditions v0.68/v0.69, le mode de survol et les assets du centre déjà livré. Le serveur ouvre la v0.69 dans le navigateur et reste lié à la machine locale. `Ctrl+C` l’arrête. La préparation du jeu livré ne télécharge aucune donnée. Prévoir au moins 1 Go libre en plus du dépôt pour les sorties et fichiers temporaires ; les imports géographiques peuvent demander davantage.

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Sous Windows, remplacez `python3` par `python`. Utilisez `--port 8766` si nécessaire. Les anciennes commandes conservées dans `game/` visent les éditions antérieures : le lanceur à la racine choisit la version actuelle.

Le bouton **« Survoler la métropole »** ouvre l’explorateur indépendant. Sa carte propose les 92 communes ; il affiche les données effectivement installées, avec un repli explicitement marqué sur le centre partiel. Le survol n’utilise aucune sauvegarde de campagne. Clavier ZQSD/WASD ou flèches, souris pour regarder, Espace pour monter, C pour descendre et Maj pour accélérer.

## Ce qui change en v0.69

- Un lot de **14 279 références IGN à l’égout** est intégré au socle, dont 14 258 identités nouvelles. Elles décrivent la hauteur à l’égout et le pied du bâtiment ; les toitures non relevées restent approximatives. Les déclarations OSM prioritaires sont conservées.
- Les parties documentées de **9 bâtiments composites** deviennent visibles sans être englouties par une enveloppe pleine générique. Les emprises résiduelles restent identifiées comme non reconstituées ; aucun volume ou obstacle n’est inventé pour les combler.
- **26 toits pyramidaux et 15 dômes** des données livrées sont admissibles aux nouveaux profils paramétriques. Leur forme est inférée à partir des paramètres disponibles ; il ne s’agit pas d’un relevé architectural. Les toits à un pan et les cours intérieures restent préservés.
- Les profils **à deux pans et à croupes** exploitent les hauteurs OSM explicites et les contours complets compatibles. L’audit métropolitain trouve **9 toits à deux pans et l’Ombrière du Vieux-Port** nouvellement modélisables. Les pignons suivent le faîtage ; les couvertures ouvertes restent visibles du dessous. Les formes insuffisamment documentées restent approximatives.
- **72 voies couvertes ou intérieures** sont reclassées : les chaussées injustifiées au niveau du MNT sont retirées, avec conservation des recouvrements routiers valides. Les ouvrages sans altitude connue ne deviennent pas des routes plates.
- Le socle existant est préparé en **quatre couches vérifiables par cellule** : vecteurs, relief, surfaces et navigation. Les outils d’import, de préparation et d’assemblage permettent de produire des éditions supplémentaires sans les activer automatiquement dans la campagne.
- Les **51 809 cellules vectorielles métropolitaines** disposent aussi de leur navigation préparée, validée indépendamment avec le moteur historique et les segments OSM natifs. Les restrictions, accès et barrières sont conservés ou refusés prudemment. Cette préparation ne certifie pas les déplacements physiques et n’active pas de nouvelle campagne.
- Un diagnostic de fidélité distingue les sources OSM/IGN, les estimations et les zones encore inconnues. Le périmètre officiel des 92 communes est consultable dans l’espace de développement.
- Le survol distingue les paysages OSM : forêts, plages, roches, cultures et carrières. Les eaux intérieures sans altitude déclarée sont colorées sur le relief valide ; mers, ports et baies gardent leur cote visuelle conventionnelle de 0 m, qui n’est pas un relevé de marée.
- Un outil de **paquet portable vérifié** permet d’exporter, contrôler et réinstaller le cache métropolitain sans dépendances externes ; les données volumineuses restent hors Git.

L’ambiance cyberpunk et les sauvegardes v0.68 sont conservées. Les lumières de façade sont une interprétation artistique stable entre cellules. Le mode « Sans filtre » retire l’étalonnage coloré ; il ne supprime pas les lumières.

## Fidélité actuelle

Les coordonnées utilisent **Lambert-93 / EPSG:2154**, avec des unités en mètres, et le datum altimétrique NGF-IGN69. La campagne conserve **17 689 altitudes IGN échantillonnées à 25 m** ; le survol métropolitain utilise les rasters natifs IGN à **5 m**, éditions d’archives de décembre 2022. Les données absentes restent absentes : 71 secteurs de relief sont partiels. Ce pas ne garantit pas la précision des marches, trottoirs ou ouvrages.

Avant les ajouts v0.69, le socle original audité avait **500 objets bâtis sur 34 986** avec hauteur OSM déclarée ou appariement IGN, soit **1,4291 % des objets**, parties comprises. Le lot de 14 279 références du socle et les 299 391 appariements de l’édition métropolitaine améliorent ce point, sans mesurer la fidélité architecturale. Les hauteurs encore inconnues restent estimées par étages ou procéduralement. Cent voies sur les 7 723 du socle possèdent une largeur OSM déclarée ; la plupart des largeurs métropolitaines restent aussi estimées.

La Major conserve notamment environ **844,4 m² d’emprise résiduelle dont le volume reste inconnu**. Ces zones n’ont pas de volume, collision ou occlusion de bâtiment fabriqués. Une construction partiellement visible ne constitue donc pas un monument intégralement reproduit.

L’audit détaillé des 71 secteurs de relief partiels ne trouve aucun raster absent. Les 1 933 nœuds utiles manquants situés dans le contour restent à moins de 11,03 m de sa limite côtière ; les autres nœuds manquants sont hors contour. Les 92 destinations ont une altitude source disponible. Ces constats ne justifient aucun comblement artificiel du masque IGN.

[Documentation de la v0.69, commandes et limites](game/README_v69.md).
[État chiffré et empreintes de la livraison métropolitaine](game/data/v69/METROPOLE_DELIVERY.json).
[Exporter et réinstaller le cache vérifié](game/tools/metropole/README_world_bundle.md).

## Développer et vérifier

Les fichiers originaux v0.67 et leurs empreintes restent conservés. Les HTML, rapports de build et assets de `game/data/v69/world/` sont générés dans des chemins ignorés par Git.

```sh
python3 lancer.py --prepare-only
python3 game/build_v69.py --verify
python3 game/tools/metropole/bootstrap.py --verify
python3 game/tools/serve_v69.py --no-browser
```

Pour les contrôles JavaScript, utiliser Node.js 18 ou plus récent :

```sh
node game/tests/v67/core.test.cjs
node --test game/tests/v68/architecture.test.cjs game/tests/v68/renderer.test.cjs game/tests/v68/visual-profile.test.cjs
node game/tests/v68/persistence.test.cjs
node --test game/tests/v69/*.test.cjs
```

Les tests Python et les outils GIS facultatifs sont détaillés dans [README_v69.md](game/README_v69.md). Le contrôle Chromium avec Playwright reste disponible dans `game/tests/v68/browser_smoke.py`, avec `--version 0.69` et une URL de serveur pointant sur le HTML v0.69. Ces vérifications ne certifient ni une campagne humaine complète ni une reproduction métropolitaine 1:1.

## Sources

- **OpenStreetMap**, contributeurs OSM, ODbL 1.0 : extrait Marseille fourni, instantané déclaré du 18 septembre 2026, conservé pour la campagne ; extrait régional Geofabrik du **24 octobre 2026** pour les 51 809 cellules vectorielles métropolitaines, toutes acceptées par le validateur du moteur.
- **IGN — RGE ALTI**, Licence Ouverte 2.0 : échantillonnage historique à 25 m pour la campagne ; archives natives à **5 m des départements 13, 83 et 84**, éditions de décembre 2022, pour le survol métropolitain. Les NoData sont conservés ; la date précise des relevés n’est pas déclarée par ces reçus.
- **IGN BD TOPO**, Licence Ouverte 2.0 : les 14 279 correspondances du socle sont intégrées par une preuve compacte livrée dans le dépôt ; leur hauteur décrit l’égout du toit, pas son faîtage. Le rapport complet et un catalogue WFS séparé de 947 118 objets IGN intersectant le contour métropolitain sont conservés hors dépôt. L’activation de la nouvelle édition métropolitaine reste distincte des sauvegardes de campagne.
- **Etalab / INSEE / DGCL**, Licence Ouverte 2.0 : composition officielle des EPCI 2026, paquet `@etalab/decoupage-administratif` 6.0.0, référence AMP `200054807`. Cette source documente l’appartenance administrative. Un contour distinct de ces 92 communes a été acquis et contrôlé via l’API géographique ; son millésime géométrique n’est pas indiqué par le service.
