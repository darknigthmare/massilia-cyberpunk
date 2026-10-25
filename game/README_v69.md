# v0.69 — Marseille augmentée et chantier métropolitain

La v0.69 améliore les géométries du socle de Marseille et ajoute les outils nécessaires à une extension par cellules. Le périmètre demandé est **toute la métropole Aix-Marseille-Provence**, identifiée par le SIREN `200054807`. Le fichier [territory.json](data/v69/territory.json) contient les **92 communes de la référence administrative 2026**.

La partie jouable livrée reste **168 cellules de 250 m, soit 10,5 km² du centre de Marseille**. La liste des communes, un import vectoriel ou la présence d’un manifeste ne prouvent pas que tout ce territoire est reproduit ou jouable.

Le **survol indépendant** dispose désormais dans cet environnement du paquet métropolitain complet préparé : **52 020 secteurs**, dont **51 809 avec vecteurs OSM** et **211 de relief seul**, avec relief IGN à 5 m, surfaces routières et **299 391 appariements IGN à l’égout** (326 058 fragments de cellules). Les 16 parents et 267 parties associés ont leur preuve propre ; les volumes résiduels inconnus restent absents. Le [rapport de livraison](data/v69/METROPOLE_DELIVERY.json) conserve les quantités, dates, empreintes et limites.

Les datasets lourds ne sont pas dans Git. Le dossier local préparé est `game/data/v69/metropole/` ; les sources et preuves complètes restent dans `/workspace/massilia-geodata-generated/`. Le survol utilise ce cache automatiquement. Sans lui, un nouveau clone affiche explicitement le centre partiel. Le paquet métropolitain n’introduit pas de navigation physique ou de migration de campagne et ne certifie pas une architecture 1:1 complète.

## Lancement et reconstruction

Toutes les commandes ci-dessous partent de la racine du dépôt. Le jeu nécessite seulement Python 3.11+ et un navigateur WebGL 2. Sous Windows, utiliser `python` à la place de `python3` ou le `LANCER_JEU.cmd` de la racine.

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Le lanceur restaure les cinq parties de données de `payload/`, vérifie les 27 fichiers originaux et reconstruit successivement v0.68 et v0.69. La v0.69 génère également le paquet du socle existant dans `game/data/v69/world/`. Le serveur local démarre sur le port 8765 ; `--port 8766` choisit un autre port. Aucune acquisition distante n’est nécessaire pour ces étapes.

Pour travailler directement sur la v0.69 après préparation :

```sh
python3 game/build_v69.py
python3 game/build_v69.py --verify
python3 game/tools/metropole/bootstrap.py --verify
python3 game/tools/serve_v69.py --no-browser
```

Les fichiers originaux et la baseline restent vérifiés. Les transformations v0.69 sont appliquées au document reconstruit et aux couches dérivées ; elles ne réécrivent pas le PBF OSM ou les mesures IGN d’origine. Les HTML, le rapport `BUILD_REPORT.json` et le répertoire `world/` sont des sorties générées.

## Survol indépendant

Le bouton **« Survoler la métropole »** ouvre `metropole-viewer.html`, construit automatiquement par le lanceur. Il permet le vol libre et les destinations des 92 communes, sans charger les états ou sauvegardes de campagne. La carte indique le territoire effectivement disponible ; le centre livré reste un repli explicitement partiel quand le paquet métropolitain n’est pas installé.

```sh
python3 game/tools/build_metropole_viewer.py
python3 game/tools/build_metropole_viewer.py --verify
```

L’explorateur utilise `data/v69/metropole/manifest.json`, puis le paquet `data/v69/world/manifest.json` en cas d’absence. Les données restent locales, sans CDN. Les géométries et le cache sont bornés, les anciens chargements sont annulés lors d’un changement de destination et les buffers GPU sont libérés. Un même ensemble de cellules visibles retrouve exactement sa géométrie après un aller-retour, indépendamment des fragments restés en cache et de l’ordre d’arrivée des données. Les emprises, cours et murs de découpe suivent les sources ; les altitudes manquantes restent absentes. Ce mode de survol ne constitue pas une migration de la campagne ni une validation des déplacements au sol.

## Données connues, estimations et géométries inconnues

Le repère commun est **EPSG:2154**, en mètres : X local vers l’est et Z local vers le sud. Le relief garde le datum **NGF-IGN69**. Le socle contient 51 414 objets géographiques uniques répartis en 57 672 fragments de cellules, dont 34 986 objets bâtis et 7 723 voies. Un objet bâti peut être une partie de bâtiment ; ces nombres ne désignent pas autant de constructions indépendantes.

L’inventaire de hauteur du **socle original audité** est le suivant, avant les nouvelles références intégrées en v0.69 :

| Origine de la hauteur | Objets bâtis |
| --- | ---: |
| Déclaration OSM exploitable | 477 |
| Appariement IGN BD TOPO déjà livré | 23 |
| Estimation à partir des étages | 5 140 |
| Estimation procédurale | 29 346 |

Ces 500 déclarations/appariements du socle original représentent **1,4291 % des objets**. Ils comprennent 273 parties de bâtiment ; les autres objets possèdent 204 hauteurs OSM et 23 références IGN. La v0.69 intègre un lot de **14 279 références IGN à l’égout**, dont 14 258 identités nouvelles et 21 références antérieures identiques. Elles restent distinctes des hauteurs totales OSM. La preuve compacte [building-height-matches.json.gz](data/v69/building-height-matches.json.gz) lie chaque référence aux géométries et contenus exacts de ses cellules. Une hauteur d’égout ne fournit pas le profil du toit : les toitures correspondantes restent des approximations plates, explicitement étiquetées. Ces données ne certifient ni les façades, ni les intérieurs, ni les volumes de toute la ville.

Le relief de la campagne possède 17 689 nœuds valides, échantillonnés à 25 m. Le survol métropolitain utilise les données natives IGN à 5 m décrites plus bas. L’espacement de ces mesures ne donne pas les altitudes exactes des marches ou tabliers de pont. Cent voies du socle possèdent une largeur OSM ; les autres utilisent encore des estimations par nombre de voies ou classe routière. Les couleurs, fenêtres, volets et lumières cyberpunk restent distingués des mesures géographiques.

Le rapport [FIDELITY_REPORT.json](data/v69/FIDELITY_REPORT.json) est reproductible avec :

```sh
python3 game/tools/v69/fidelity_audit.py
```

Cet outil de développement utilise Node.js pour exécuter les noyaux de dimensions, de terrain et de navigation livrés. Il audite explicitement la **baseline géographique v0.66 livrée avec v0.67, avant les corrections v0.69**. Les empreintes d’entrée sont enregistrées. Ses 72 profils routiers à corriger décrivent donc le socle antérieur, pas un échec des corrections actives. Aucun ratio de couverture administrative n’est calculé sans contour territorial complet validé.

## Bâtiments composites et toits

Les preuves de [building-parts.json](data/v69/building-parts.json) associent des parties aux enveloppes par données de relation OSM vérifiées ou par inclusion géométrique unique. Neuf parents sont actuellement traités comme **partiellement reconstitués**. Les parties documentées partagent la référence de sol de leur parent et ne sont plus masquées par une boîte pleine générique.

Les emprises résiduelles restent conservées dans les données comme zones dont le volume est inconnu. Elles ne reçoivent pas de hauteur locale inventée, de collision ou d’occlusion de bâtiment. Pour la Major, 72 parties de base nulle strictement contenues couvrent environ 84,9651 % de l’emprise parent ; **844,4 m²** restent sans volume reconstitué. Les parties connues deviennent visibles, mais le monument n’est pas présenté comme terminé ou intégralement accessible.

En plus des toits à un pan déjà pris en charge, 26 empreintes pyramidales et 15 dômes du socle sont admissibles aux nouveaux modèles. Les paramètres OSM fournissent la forme déclarée et les hauteurs disponibles ; la position du sommet et le profil courbe sont **inférés**. Les emprises, cours et limites de cellule sont conservées. La borne d’erreur de triangulation d’un dôme décrit l’approximation mathématique du modèle, pas une précision de relevé du monument réel. Les formes insuffisamment renseignées restent explicitement non résolues.

La génération facultative de la preuve de parties utilise le PBF vérifié pour les relations `type=building` :

```sh
python3 game/tools/metropole/building_parts.py --pbf game/data/source/Marseille.osm.pbf
```

Cette commande demande l’environnement GIS décrit plus bas. La reconstruction normale utilise la preuve livrée et ne demande pas ces dépendances.

## Routes, surfaces et navigation

La correction v0.69 reclassifie 72 voies couvertes ou intérieures auparavant traitées comme des surfaces de sol ordinaires. Elle soustrait uniquement les surfaces injustifiées et préserve les zones couvertes également soutenues par une voie de surface valide. Les profils, couches sources et empreintes de correction sont conservés dans [road-surfaces.json](data/v69/road-surfaces.json).

Les ponts, tunnels, voies à niveau différent et accès intérieurs sans altitude d’ouvrage restent exclus des modèles de surface concernés. Les axes OSM d’escaliers et leurs attributs sont conservés, sans fabriquer de volumes de marches à partir d’un MNT à 25 m. La navigation garde les identités des nœuds OSM, les sens de circulation et les restrictions ; un croisement de lignes sur le plan ne crée pas automatiquement un carrefour.

Pour régénérer la correction livrée avec l’environnement GIS :

```sh
python3 game/tools/metropole/road_surfaces.py
```

## Paquet du socle et chargement par couches

`bootstrap.py` prépare, depuis le HTML v0.69 vérifié, un manifeste et quatre couches par cellule :

| Couche | Contenu |
| --- | --- |
| `vector` | Géométries, propriétés et empreintes de la cellule |
| `terrain` | Nœuds IGN avec masque de validité et datum |
| `surfaces` | Chaussées, cheminements et références de dimensions |
| `navigation` | Sous-ensemble sourcé du graphe, lié aux mêmes cellules |

Les tailles, SHA256, emprises et éditions sources sont vérifiées avant utilisation. Le cache d’assets est borné ; sa limite ne représente pas la mémoire totale du jeu ou du GPU. Le graphe et le catalogue historiques complets restent ceux de la campagne active.

L’espace de développement est accessible avec **Ctrl+Maj+F10**, puis **« Fidélité & périmètre métropolitain »**. Il présente le périmètre, les diagnostics et la vérification des couches de la cellule actuelle.

Une édition supplémentaire possède ses propres fichiers de préparation. La présence des quatre couches ne réalise pas la migration du catalogue d’exploration, des itinéraires, des accès physiques et de la campagne. Le chargement ne l’active donc pas automatiquement comme territoire jouable. Ne pas remplacer le paquet `game/data/v69/world/` du socle pour contourner ces contrôles.

## Préparer des éditions géographiques supplémentaires

Ces outils facultatifs servent au développement. Les dépendances sont épinglées dans [requirements.txt](tools/metropole/requirements.txt). Le jeu livré et sa reconstruction ordinaire n’en ont pas besoin. Exemple Linux/cloud, avec le venv et les sorties hors du checkout :

```sh
python3 -m venv /tmp/massilia-geodata-venv
/tmp/massilia-geodata-venv/bin/python -m pip install -r game/tools/metropole/requirements.txt
MASSILIA_GEO_PYTHON=/tmp/massilia-geodata-venv/bin/python
```

Si un venv de développement existe déjà, utiliser son interpréteur. Node.js est également nécessaire pour le calcul des profils routiers et l’audit. Les générateurs conservent les sorties existantes incompatibles ou refusent les répertoires déjà présents : choisir un nouveau chemin pour une nouvelle édition.

### 1. Vecteurs OSM et topologie native

Un reçu OSM doit fournir la licence, l’attribution et, lorsqu’elle est déclarée, l’empreinte du PBF. L’import calcule le SHA256 réel et refuse une empreinte contradictoire. Pour réutiliser les métadonnées de l’extrait livré :

```sh
python3 - <<'PY'
import json
from pathlib import Path
out = Path('/tmp/massilia-metropole')
out.mkdir(parents=True, exist_ok=True)
source = json.loads(Path('game/data/v58/SOURCE_SUMMARY.json').read_text(encoding='utf-8'))['source']
(out / 'osm-receipt.json').write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
PY
```

Exemple limité à une cellule du socle, dans le repère historique :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/import_tiles.py \
  --pbf game/data/source/Marseille.osm.pbf \
  --receipt /tmp/massilia-metropole/osm-receipt.json \
  --bounds-l93 892826.6480966414 6247149.566415883 893076.6480966414 6247399.566415883 \
  --output /tmp/massilia-metropole/vectors
```

Sans `--bounds-l93`, l’outil prépare le périmètre disponible dans le PBF, sous les budgets configurés. Ce n’est pas une acquisition de toute la métropole. `--boundary` accepte un polygone WGS84 fourni comme filtre ; la seule présence de ce filtre ne prouve pas son exhaustivité administrative.

Une préparation bornée de tout l’extrait local disponible a aussi été réalisée dans cet environnement : **18 385 tuiles vectorielles et 698 543 objets canoniques**, avec 20 géométries rejetées et mises en quarantaine. Ce total compte plusieurs catégories d’objets : les bâtiments et leurs parties ne doivent pas être additionnés comme autant de bâtiments uniques. L’extrait source couvre l’emprise WGS84 `[5.277, 43.142, 5.72, 43.438]` ; il dépasse certaines limites de la métropole et n’inclut pas l’ensemble d’Aix ou de Berre. Il ne crée aucune zone jouable supplémentaire.

La commande utilisée depuis la racine, avec l’interpréteur GIS installé dans cet environnement, est :

```sh
/workspace/.massilia-geodata-venv/bin/python game/tools/metropole/import_tiles.py \
  --pbf game/data/source/Marseille.osm.pbf \
  --receipt game/data/v69/OSM_SOURCE_RECEIPT.json \
  --output /workspace/massilia-geodata-generated/vector-source-full-bounded \
  --max-tiles 100000 \
  --bounds-l93 884404.9563583039 6229644.677801095 921401.9343122083 6263671.2007139735
```

Ces limites proviennent de l’enveloppe projetée des quatre coins de l’en-tête PBF. Les autres budgets restent à leurs valeurs par défaut : 12 000 fragments, 300 000 coordonnées et 16 Mio décodés par tuile. Les sorties sont **hors dépôt**, dans l’environnement cloud ; elles ne sont pas présentes dans un nouveau clone. Le manifeste de cette préparation porte le SHA256 `58265226727744903fed148578aa46591556e1f1162c1ff2c86e2e72fd1c7d88`. La vérification globale des empreintes et des géométries est une étape distincte de la génération ; ces chiffres ne certifient pas la fidélité architecturale.

### 2. Relief, avec validité explicite

Pour copier les nœuds existants sans rééchantillonnage :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/v69/terrain_tiles.py from-grid \
  --grid game/data/v58/terrain.ign.json \
  --cells /tmp/massilia-metropole/vectors/manifest.json \
  --output /tmp/massilia-metropole/terrain
```

Hors couverture, les données manquent ou restent NoData ; elles ne deviennent pas un sol plat. Pour des MNT GeoTIFF locaux supplémentaires :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/v69/terrain_tiles.py from-geotiff \
  --raster /chemin/vers/mnt-ign.tif \
  --receipt /chemin/vers/recu-mnt.json --step 5 \
  --cells /tmp/massilia-metropole/vectors/manifest.json \
  --output /tmp/massilia-metropole/terrain-mnt
```

Les rasters doivent être monobandes, en EPSG:2154, orientés nord en haut et alignés sur un même carroyage natif. Le reçu déclare `provider`, `product`, `license`, `attribution`, `units: "m"` et `verticalDatum: "NGF-IGN69"`. Les empreintes de fichiers sont enregistrées ; une empreinte fournie est vérifiée. Le pas 1, 5 ou 25 m ne peut pas être plus fin que la résolution source. Une interpolation avec un coin NoData ou des mesures superposées contradictoires ne produit pas une altitude inventée.

### Relief natif métropolitain à 5 m

L’acquisition complète utilise les archives officielles **RGE ALTI 5 m des départements 013, 083 et 084, éditions de décembre 2022**. Le CLI conserve les catalogues, archives, reçus, MD5 officiels et SHA256. Exemple d’acquisition explicite :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/v69/acquire_terrain.py native-fetch \
  --boundary game/data/v69/acquisition/amp-boundary-2026-10-25.geojson \
  --step 5 --department 013 --department 083 --department 084 \
  --output /tmp/massilia-metropole/native-archives
```

La commande `native-import` accepte des paires répétées `--archive` et `--archive-receipt` avec le même contour. Elle extrait les dalles utiles, vérifie les pixels et conserve leurs centres métriques, le datum NGF-IGN69 et les NoData lors de la conversion GeoTIFF. La dépendance facultative `py7zr` est épinglée dans `requirements.txt`.

Dans cet environnement, 227 ASC contrôlés ont produit **185 rasters uniques**, les 42 doublons étant identiques. Le relief dérivé couvre **52 020 cellules à 5 m** : 51 949 complètes et 71 partielles, sans cellule entièrement manquante. Les 204 880 raccords et 17 247 420 nœuds communs sont identiques. Les sorties et leurs preuves sont dans `/workspace/massilia-geodata-generated/terrain-amp-native5m-2022/` ; elles restent absentes d’un nouveau clone.

Les définitions administratives de relief utilisent le schéma distinct `soma-metropole/terrain-target-cells/1`, avec empreinte du contour. Elles ne prétendent pas posséder des objets OSM. Ce relief constitue une nouvelle édition cohérente : il n’est pas greffé sur l’ancienne grille de campagne à 25 m. Les exports WMS exploratoires sont exclus, car leur interpolation des NoData produit des altitudes côtières incorrectes.

Le générateur reproductible du contour complet est [build_terrain_coverage.py](tools/v69/build_terrain_coverage.py) :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/v69/build_terrain_coverage.py \
  --boundary game/data/v69/acquisition/amp-boundary-2026-10-25.geojson \
  --raster-index /chemin/vers/native-import/raster-index.json \
  --receipt /chemin/vers/native-import/source-receipt.json \
  --output /tmp/massilia-metropole/terrain-complet --workers 2
```

`--plan-only` produit uniquement `plan.json` et `target-cells.json`. La génération complète publie atomiquement le manifeste et ses batches ; elle conserve les dossiers existants, limite les sorties à 2 Gio et réserve 4 Gio de disque par défaut. Aucun téléchargement ou objet vectoriel n’est créé par ce générateur.

### 3. Surfaces et navigation

Ces deux traitements utilisent le même manifeste vectoriel et les axes natifs du PBF :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/surface_tiles.py \
  --manifest /tmp/massilia-metropole/vectors/manifest.json \
  --baseline game/baseline/v66.html --output /tmp/massilia-metropole/surfaces

"$MASSILIA_GEO_PYTHON" game/tools/metropole/navigation_tiles.py \
  --manifest /tmp/massilia-metropole/vectors/manifest.json \
  --output /tmp/massilia-metropole/navigation
```

Les surfaces distinguent largeurs OSM et estimations, préservent les trous et ne créent pas de passages piétons automatiquement. Les graphes conservent les identités natives et les restrictions ; les permissions conditionnelles ou ouvrages non modélisés sont traités prudemment.

### 4. Assemblage d’une édition de préparation

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/assemble_world.py \
  --vectors /tmp/massilia-metropole/vectors/manifest.json \
  --terrain /tmp/massilia-metropole/terrain/manifest.json \
  --surfaces /tmp/massilia-metropole/surfaces/surface-manifest.json \
  --navigation /tmp/massilia-metropole/navigation/manifest.json \
  --territory game/data/v69/territory.json \
  --output /tmp/massilia-metropole/world
```

L’assembleur vérifie les empreintes, éditions sources, emprises et liaisons entre couches. Les couches absentes restent `null`, les NoData restent invalides, et `activationPerformed` reste `false`. Même une préparation techniquement complète ne certifie pas les accès physiques ou la couverture des 92 communes.

### Hauteurs IGN BD TOPO locales

Le matcher facultatif traite des emprises IGN fournies en EPSG:2154 avec un reçu de SHA256, licence, date, unités métriques et datum NGF-IGN69 :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/building_heights.py \
  --manifest /tmp/massilia-metropole/vectors/manifest.json \
  --ign /chemin/vers/bdtopo-batiments.geojson \
  --receipt /chemin/vers/recu-bdtopo.json \
  --output /tmp/massilia-metropole/building-heights.json
```

Les champs par défaut sont `CLEABS`, `HAUTEUR`, `Z_MIN_SOL`, configurables explicitement par le reçu. L’appariement exige IoU ≥ 0,90 et marges avant/réciproque ≥ 0,15. Il préserve les hauteurs OSM, exclut les parties actives et ne déduit pas une hauteur relative d’un Z de toit absolu. Les correspondances sont liées au triplet source/identifiant/géométrie et aux cellules concernées.

Le matcher a été testé sur fixtures, puis exercé sur une acquisition réelle du WFS officiel `BDTOPO_V3:batiment`, édition déclarée du 15 juin 2026. Pour le rectangle central Lambert-93 `[891326.6480966414, 6245649.566415883, 894576.6480966414, 6248899.566415883]`, 16 sous-requêtes et 18 pages triées ont fourni 34 205 objets IGN uniques après suppression de 2 846 doublons identiques de frontières. Les réponses, les comptes complets, les URL, dates UTC et empreintes sont conservés dans `/workspace/massilia-geodata-generated/acquisition/ign-bdtopo-socle-2026-06-15/`, **hors dépôt et absents d’un nouveau clone**.

Sur les 34 986 objets bâtis des 168 cellules, **14 279 correspondances** satisfont les gardes conservatrices. Les 20 707 autres objets sont refusés, notamment pour emprise incomplète, IoU insuffisant, voisinage non vérifiable, parties actives ou déclaration OSM préservée. Le GeoJSON source porte le SHA256 `ae7c6c412aa2250c70ea534e80e08454e931ed6bd0a9ad1cf69b985addb3d1fb` ; la preuve `matches.json`, validée avec son checksum interne, porte le SHA256 `603e851584a688cc5d59182b1d1719bb53683299bf40da85e82deb9a6fcbbf07`.

Le reçu utilise les champs WFS `cleabs`, `hauteur` et `altitude_minimale_sol`. Selon le descriptif officiel BD TOPO, cette **hauteur va du pied bas du bâtiment au point haut de la gouttière ou du bord de toit** : elle ne mesure pas le faîtage. Zéro signifie inconnu ou non significatif. Les unités en mètres, le datum continental IGN69, la licence et le document de définition sont liés aux preuves. Ces appariements fournissent une hauteur de façade ; ils ne constituent pas un relevé complet du volume. La preuve compacte livrée de 14 279 références est intégrée au socle v0.69 et à ses surfaces de survol. L’édition métropolitaine séparée dispose de 299 391 correspondances assemblées dans son propre cache.

## Acquisition IGN explicite et catalogue métropolitain

L’outil [acquire_bdtopo.py](tools/metropole/acquire_bdtopo.py) télécharge uniquement à la demande, avec l’environnement GIS. Il prépare un catalogue séparé, sans intervenir dans le lanceur ou le build :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/acquire_bdtopo.py \
  --boundary game/data/v69/acquisition/amp-boundary-2026-10-25.geojson \
  --source-receipt /chemin/vers/metadata-ign.json \
  --output /tmp/massilia-metropole/ign-bdtopo \
  --source-budget 1500000000 --max-requests 1000 --workers 2 --step 4000
```

Le reçu d’entrée doit déclarer `provider`, `product`, `license`, `attribution`, `date` au format ISO, `crs: "EPSG:2154"`, `units: "m"`, `verticalDatum: "NGF-IGN69"`, `heightKind: "eaves"`, `heightMeaning`, ainsi que les SHA256 `sourceMetadataSHA256` et `sourceSpecificationSHA256` des preuves officielles consultées. `fields` vaut `{"ignId":"cleabs","height":"hauteur","groundAltitude":"altitude_minimale_sol"}`. La date doit correspondre au millésime déclaré par les capacités WFS lors de l’acquisition ; l’outil conserve ces métadonnées déclarées sans prétendre à une certification indépendante de leur authenticité.

Les budgets ne peuvent dépasser 1,5 Go de réponses conservées, deux requêtes simultanées, 5 000 objets et 16 Mio par page. Chaque sous-requête utilise un tri `cleabs`, des comptes complets et une pagination contrôlée. Une réponse vide peut avoir `crs:null` ; toute réponse contenant des objets doit déclarer EPSG:2154. Les contradictions d’identité sont refusées. Les géométries qui intersectent le contour sont conservées **entières** dans SQLite ; elles ne sont pas découpées à la limite administrative. Les sources invalides sont mises en quarantaine sans réparation implicite.

Les sorties comprennent `configuration.json`, les pages et leurs reçus dans `pages/`, `source-metadata.json`, `boundary.geojson`, `buildings.sqlite`, `progress.json`, puis `source-index.json` quand toutes les requêtes sont terminées. Leurs références internes sont relatives. Une interruption laisse un état incomplet ; relancer exactement la même commande avec `--resume` vérifie configuration, sources et empreintes avant de continuer. Un budget ou une source modifiés sont refusés. La reprise d’un catalogue déjà complet n’effectue aucun nouveau téléchargement. Les lots issus de scripts expérimentaux antérieurs ne sont pas implicitement convertis vers ce format.

Une acquisition réelle AMP, antérieure à cette promotion de l’outil, a été menée à terme dans `/workspace/massilia-geodata-generated/acquisition/ign-bdtopo-amp-2026-06-15-r2/` : **947 118 objets IGN uniques** intersectent le contour officiel des 92 communes. Les 261 sous-requêtes et 383 pages représentent 1 397 485 416 octets de réponses sources. La validation indépendante a relu toutes les pages, les URL et comptes, les objets retenus et les exclusions hors contour, puis l’intégrité SQLite. Aucune géométrie n’a été découpée et aucune n’a été mise en quarantaine. L’index porte le `sourceSHA256` `95734a65cb9c18d7de50107b855e24cab5f0e2952140e0f98de0e920afc7456e` ; SQLite porte le SHA256 `07c19c1f28ec5503dc633d6875b8e7ec45f6e26ae52b90d0a2b5c52bf2d6ff15` ; `VALIDATION.json` conserve le détail des contrôles.

Ce catalogue et ses sources restent **hors dépôt et absents d’un nouveau clone**. Ils fournissent les bâtiments IGN de l’édition WFS déclarée du 15 juin 2026 intersectant le contour acquis. Leur appariement métropolitain a été effectué par partitions avec voisinages complets, puis lié aux véritables cellules ; ce catalogue seul ne remplace ni le relief ni la validation de déplacements physiques.

## Appariement des catalogues et sidecars de cellules

[match_catalogues.py](tools/metropole/match_catalogues.py) traite les catalogues publiés par partitions bornées. Il réutilise les seuils et la priorité OSM du matcher strict, avec un index IGN dérivé séparé : le million d’objets IGN n’est pas converti en géométries Shapely en mémoire. Exemple après publication et vérification du manifeste OSM correspondant :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/match_catalogues.py match \
  --osm-manifest /chemin/vers/vecteurs-publies/manifest.json \
  --ign-index /chemin/vers/ign-publie/source-index.json \
  --boundary game/data/v69/acquisition/amp-boundary-2026-10-25.geojson \
  --osm-pbf /chemin/vers/source-osm-verifie.osm.pbf \
  --osm-rejection-proof game/data/v69/acquisition/paca-2026-10-24.rejection-envelopes.json \
  --output /tmp/massilia-metropole/height-catalogue --step 1000
```

`--bounds-l93 ouest sud est nord` limite un échantillon par les centres d’enveloppe des objets propriétaires. Les géométries sources restent complètes. Pour chaque noyau de partition, le traitement recherche tous ses candidats IGN, puis tous les voisins OSM de ces candidats, avant de décider les marges réciproques. Il conserve donc les rivaux situés de l’autre côté d’une partition. Les candidats qui dépassent la couverture commune prouvée sont refusés. Les déclarations OSM explicites et les parties actives gardent la priorité du matcher original.

Les limites par défaut sont 20 000 objets OSM et 20 000 objets IGN par voisinage, 512 candidats par objet, 64 Mio de données natives par partition et 10 000 partitions. Un dépassement laisse une sortie non scellée et demande une partition plus petite. Les sources SQLite sont ouvertes en lecture seule, leurs empreintes sont contrôlées et un fichier WAL en cours empêche leur utilisation. Les rejets de l’import OSM doivent être identifiés comme hors bâti ; `--osm-pbf` permet de retrouver leurs tags lorsque le catalogue ne les conserve pas. Un rejet bâti sans enveloppe prouvée bloque la préparation plutôt que d’effacer un rival potentiel.

La preuve de rejets livrée est liée **uniquement** au PBF PACA du 24 octobre 2026 et à ses 53 quarantaines. Elle démontre 34 objets hors bâti, 18 objets bâtis hors contour et l’enveloppe d’un chemin bâti ouvert local. Les voisinages concernés par ce dernier restent refusés. Une autre édition exige sa propre preuve ; aucune réparation géométrique n’est appliquée.

Le résultat est `matches.sqlite` avec ses preuves canoniques et un `seal.json` liant les sources, l’algorithme, les limites et les empreintes. Chaque correspondance est liée au triplet `[sourcePBF_SHA256, canonicalId, geometrySHA256]`, à l’identifiant et au contenu IGN, avec `heightKind: "eaves"`. Les pseudo-records utilisés en interne ne deviennent pas des cellules du jeu : aucune liaison de cellule fictive n’est publiée. L’outil ne modifie pas le lot de 14 279 références du socle.

Pour lier ensuite ce catalogue aux véritables cellules de l’import :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/match_catalogues.py sidecars \
  --seal /tmp/massilia-metropole/height-catalogue/seal.json \
  --vectors /chemin/vers/vecteurs-publies/manifest.json \
  --output /tmp/massilia-metropole/height-sidecars
```

Chaque sidecar lie le `cellId`, le vrai `contentSHA256`, le SHA du fichier vectoriel et le même instantané PBF. Les déclarations OSM restent prioritaires. Ces fichiers préparent des références pour une édition supplémentaire ; leur présence n’active ni un territoire ni une campagne.

Un échantillon réel du centre, construit avec l’ancien catalogue canonique publié et le nouveau catalogue IGN AMP, a examiné 940 objets propriétaires sur deux partitions et accepté **558 correspondances**. Le pic de voisinage était de 866 objets OSM et 757 objets IGN. Les sidecars de neuf cellules réelles contiennent les mêmes 558 identités, réparties en 610 fragments ; ces fragments ne sont pas autant de bâtiments distincts. Les sorties sont conservées hors dépôt sous `acquisition/catalogue-match-sample-centre-v3/` et `acquisition/catalogue-sidecar-sample-centre-v3/` dans cet environnement. Ce résultat n’est pas un appariement de toute la métropole.

L’exécution métropolitaine complète suivante a traité **1 041 023 objets bâtis propriétaires**, retenu **299 391 correspondances** et refusé ou préservé les 741 632 autres objets. Les 51 809 sidecars contiennent 326 058 fragments, sans dupliquer une identité IGN entre bâtiments. Les rapports de validation complets sont conservés dans `heights-amp-2026-06-15/` et `surfaces-amp-with-heights-2026-06-15/` sous le dossier de travail hors dépôt.

### Intégrer les références et les parties au survol

Les références validées peuvent enrichir les surfaces sans recalculer ni modifier leurs chaussées :

```sh
python3 game/tools/metropole/attach_height_references.py \
  --vectors /tmp/massilia-metropole/vectors/manifest.json \
  --surfaces /tmp/massilia-metropole/surfaces/surface-manifest.json \
  --heights /tmp/massilia-metropole/height-sidecars/manifest.json \
  --output /tmp/massilia-metropole/surfaces-with-heights
```

Pour le survol, assembler vecteurs et relief avec `assemble_world.py --include-terrain-only` conserve aussi les secteurs de MNT sans vecteurs. `--navigation` reste facultatif ; son absence ne produit pas un graphe artificiel. Préparer les parties et enrichir cette édition **avant de la servir** :

```sh
"$MASSILIA_GEO_PYTHON" game/tools/metropole/catalogue_building_parts.py \
  --manifest /tmp/massilia-metropole/vectors/manifest.json \
  --pbf /chemin/vers/source-osm-verifie.osm.pbf \
  --boundary game/data/v69/acquisition/amp-boundary-2026-10-25.geojson \
  --osm-rejection-proof game/data/v69/acquisition/paca-2026-10-24.rejection-envelopes.json \
  --output /tmp/massilia-metropole/building-parts.json

python3 game/tools/metropole/attach_world_parts.py \
  --world /tmp/massilia-metropole/world \
  --parts /tmp/massilia-metropole/building-parts.json

python3 game/tools/metropole/attach_world_surfaces.py \
  --world /tmp/massilia-metropole/world \
  --surfaces /tmp/massilia-metropole/surfaces-with-heights/surface-manifest.json \
  --progress
```

Ces ajouts vérifient les empreintes et liaisons de cellules, conservent les assets de relief et vecteurs et remplacent atomiquement le manifeste final. Les 211 cellules métropolitaines de relief seul restent sans bâtiment ni route fabriqués. Le paquet installé utilise ce parcours ; la navigation physique demeure absente et l’activation de campagne reste désactivée.

## Vérifications et accès aux données

Les commandes courantes de validation sont :

```sh
node game/tests/v67/core.test.cjs
node --test game/tests/v68/architecture.test.cjs game/tests/v68/renderer.test.cjs game/tests/v68/visual-profile.test.cjs
node game/tests/v68/persistence.test.cjs
node --test game/tests/v69/*.test.cjs
python3 -m unittest discover -s game/tests/v69 -p 'test_*.py'
"$MASSILIA_GEO_PYTHON" -m unittest discover -s game/tests/metropole -p 'test_*.py'
python3 lancer.py --verify
```

Les tests de rasters demandent également le venv GIS pour exécuter tous leurs cas. Avec Chromium et Playwright installés, après démarrage du serveur v0.69 dans un autre terminal :

```sh
python3 game/tests/v68/browser_smoke.py --version 0.69 \
  --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_69.html
```

Le contrôle exerce le monde réel livré, les préférences, la sauvegarde groupée et des cas architecturaux. Un succès logiciel ne remplace pas un relevé de façades, un contrôle sur GPU physique ou une campagne humaine complète.

Les acquisitions publiques utilisent `data.geopf.fr`, `geo.api.gouv.fr` et `download.geofabrik.de`, dont les réponses et fichiers ont été vérifiés dans cette instance. Ces domaines et les scripts de préparation sont enregistrés dans le brouillon de configuration cloud ; son enregistrement ne remplace pas la revue et la publication de l’environnement. Les nouvelles instances doivent retrouver les sources préparées ou relancer les acquisitions explicites avec leurs reçus et empreintes.

L’appartenance des 92 communes provient du paquet Etalab `@etalab/decoupage-administratif` 6.0.0, compilant les références INSEE/DGCL 2026, sous Licence Ouverte 2.0 ; l’intégrité de l’artefact est conservée dans `territory.json`. Un contour distinct, acquis via `geo.api.gouv.fr`, est référencé dans `territory.json` avec ses sources et empreintes. Les 92 codes correspondent exactement à la référence administrative, l’union géométrique est valide et conserve les îles ; le service ne précise pas le millésime de ses géométries. La disponibilité du contour ne signifie pas que les données de relief, voirie et bâtiments couvrent toutes les communes. Le PBF initial, le MNT livré et l’acquisition BD TOPO centrale ne sont pas présentés comme une acquisition complète de la métropole ni comme un chantier 1:1 terminé.
