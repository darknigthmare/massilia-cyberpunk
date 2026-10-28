# v0.71 — Poursuite, inspection architecturale et itinéraires visibles

Cette édition poursuit trois chantiers en parallèle : les contacts réellement observés dans les poursuites, la lecture des sources architecturales et l’utilisation des itinéraires du survol. *Syndicate*, *Cyberpunk 2077* et *E.Y.E: Divine Cybermancy* restent des références pour les choix tactiques et l’intrusion. Les mécaniques, le contenu et le rendu décrits ici sont ceux de Massilia.

## Lancer et conserver sa partie

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Après préparation, `python3 game/tools/serve_v71.py --no-browser` démarre directement le serveur. La campagne s’ouvre dans `SOMA_MASSILIA_URBAIN_v0_71.html` ; le bouton de survol ouvre `metropole-viewer-v71.html`, dont le retour conserve la partie. Python 3.11+ et un navigateur WebGL 2 suffisent. Le jeu et sa reconstruction n’exigent ni Node, ni outil GIS, ni téléchargement de données.

Un lancement normal réutilise les sorties préparées si leurs empreintes, sources transitives, rapports et assets du centre restent conformes. Les cinq payloads et 27 originaux sont toujours contrôlés. Une modification ou corruption provoque la préparation complète ; les dates et tailles seules ne suffisent pas à valider ce cache. `--prepare-only` reconstruit et enregistre un reçu ; `--verify` effectue la chaîne complète en lecture seule. Le reçu `data/v71/LAUNCH_CACHE.json` est local et ignoré par Git. Le diagnostic facultatif `python3 -S game/tools/launch_cache_v71.py --check` indique si sa réutilisation est possible.

Les sauvegardes v0.70 restent compatibles. Aucun domaine `core.v71` n’est ajouté. Les capacités héritées utilisent toujours `core.v70` et le cyberdeck v42 : **Maj+F1** pour le Cortex, **Maj+F2/F3/F4** pour Écho, Rempart et Ancrage. Les consommables **F1–F4** sont préservés. Voir [README_v70.md](README_v70.md) pour leurs coûts et délais.

## Police et anciennes sentinelles

Les policiers à pied, robots de sécurité, drones policiers et véhicules de poursuite utilisent le noyau de perception v70. La visibilité respecte les obstacles réellement évalués par le jeu ; les pas et tirs restent localisés à leur point d’émission, même lorsque le son est coupé. Le niveau de recherche policier seul ne donne plus la position courante du joueur.

Un contact vu ou entendu fournit une dernière position connue, conservée au maximum cinq secondes sans nouveau contact. La poursuite se dirige vers ce souvenir. Les attaques requièrent une acquisition confirmée, et la reddition volontaire requiert un officier qui voit réellement le joueur. La posture C/Ctrl et les effets d’aveuglement, d’immobilisation et de brouillage restent pris en compte par leurs propriétaires existants.

Les unités tactiques ne sont plus traitées une seconde fois par le noyau historique. Les boss et caméras conservent leurs propriétaires ; les ICE numériques du cyberespace gardent leurs règles d’attaque et de dégâts. Les collisions, trajets routiers et conséquences corporelles/policières existants restent appliqués. La mémoire perceptive est éphémère et s’efface aux changements de zone et aux imports.

## Inspecter l’architecture visible

Visez une façade ou un toit dans le survol, puis appuyez sur **I** ou sur **« Inspecter le bâtiment »**. Le sélecteur teste les triangles réellement affichés : terrain, eau, routes et autres surfaces peuvent cacher un bâtiment. Il utilise le même sens des faces que le rendu. La lecture reste limitée à 1 500 m et 600 000 triangles, avec un statut explicite lorsque la limite est atteinte.

La fiche présente l’objet OSM, la hauteur utilisée, sa provenance, la base NGF, la forme de toit, les matériaux et les tags disponibles. Elle distingue notamment une hauteur IGN à l’égout d’un faîtage relevé, une hauteur calculée depuis les étages d’une mesure, et une palette de matériau d’une couleur déclarée. Un lien ouvre l’objet OSM correspondant. Les fenêtres et lumières cyberpunk restent une interprétation artistique.

L’inspection emprunte le verrou de scène existant et ne déclenche aucune acquisition géographique ou écriture de campagne. Elle conserve strictement les buffers de positions/couleurs du survol v0.70. L’audit des toits n’a pas fourni de nouvelle cohorte dont les paramètres suffisent à ajouter un profil : les emprises complexes ou orientations insuffisantes restent documentées comme approximatives.

## Itinéraires par voies et repères 3D

Dans **« Itinéraire local »**, marquez le départ ici, volez jusqu’à l’arrivée, puis rouvrez le panneau et analysez. L’aperçu 2D et la liste présentent les seuls axes source. Les segments consécutifs d’une même voie sont regroupés par nom et distance ; les escaliers sont indiqués. Les choix d’axes ambigus utilisent leur nom déclaré, leur identité OSM et leur écart au point.

Au retour au survol, la case **« Afficher les repères du trajet en 3D »** permet de conserver des rubans cyan sur les axes. Ils sont découpés contre les triangles natifs du MNT et suivent leurs pentes. Ils utilisent uniquement les cellules de relief complet déjà affichées. Une cellule absente, partielle ou dont la géométrie n’est pas encore affichée crée une interruption ; aucune lecture réseau supplémentaire n’est lancée pour combler ce manque. Les repères suivent la profondeur de la scène : ils ne traversent pas les bâtiments.

Le bandeau indique la longueur effectivement marquée et les limites d’affichage. **« Effacer le trajet »** retire les buffers associés. Une nouvelle analyse, une modification des points ou un changement de monde efface les anciens repères. Les graphes NAV sont libérés après le calcul ; le rendu garde uniquement les segments nécessaires à sa présentation.

Les budgets de calcul hérités restent de 36 secteurs, 12 000 nœuds, 16 000 arêtes, 64 Mio comptabilisés et trois secondes. Les repères ajoutent au plus 4 096 petits rubans, soit 884 736 octets de sommets GPU, hors leur métadonnée de trajet. La liste garde au plus 120 groupes et indique la distance restante. Les deux requêtes d’assets simultanées restent le plafond global. Les approches libres, ponts, tunnels et passages non résolus ne deviennent pas des connexions inventées ; la navigation physique métropolitaine reste inactive.

## Géographie et validation

Le monde reste celui livré en v0.69 : **92 communes, 52 020 cellules, relief IGN natif à 5 m**, 299 391 références à l’égout et 51 809 cellules avec vecteurs/surfaces/navigation. La campagne physique reste limitée aux **168 cellules du centre, soit 10,5 km²**. Le cache et l’archive portable restent hors Git ; [README_v69.md](README_v69.md) décrit leur installation et leurs limites.

```sh
node --test --test-concurrency=2 game/tests/v67/core.test.cjs game/tests/v68/*.test.cjs game/tests/v69/*.test.cjs game/tests/v70/*.test.cjs game/tests/v71/*.test.cjs
python3 -m unittest discover -s game/tests/v70 -p 'test_*.py'
python3 -m unittest discover -s game/tests/v71 -p 'test_*.py'
python3 -S game/build_v71.py --verify
python3 -S game/tools/build_metropole_viewer_v71.py --verify
```

Définir `MASSILIA_ROUTE_WORLD` vers le manifeste du cache préparé permet d’exercer les vrais graphes AMP dans les tests. Les preuves de l’édition finale sont consignées dans le [rapport de livraison v71](data/v71/FEATURE_REPORT.json) et le dossier de validation cloud. Elles ne constituent pas un relevé architectural complet : façades, toitures et dimensions manquantes restent des chantiers ouverts pour atteindre une fidélité 1:1.
