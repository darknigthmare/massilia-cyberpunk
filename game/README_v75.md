# v0.75 — Relief du centre, opérations, snipers et véhicules

Cette édition poursuit le Marseille cyberpunk de Massilia avec ses propriétaires de jeu existants. Elle prolonge la v0.74 (`bb48f68`), dont les sources restent gelées. Les références *Syndicate*, *Cyberpunk 2077* et *E.Y.E: Divine Cybermancy* orientent le contre-jeu et la lisibilité des actions.

## Lancer

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Python 3.11+ et WebGL 2 suffisent. Après préparation, `python3 game/tools/serve_v75.py --no-browser` sert directement `SOMA_MASSILIA_URBAIN_v0_75.html` et `metropole-viewer-v75.html`. Le lanceur prépare quinze builders et contrôle cinq payloads, 27 originaux, quinze HTML, treize rapports et les assets des 168 cellules du centre. Les lancements suivants vérifient les contenus avant de réutiliser leur reçu ; les dates seules ne suffisent pas. HTML, rapports de build et cache métropolitain restent hors Git.

## Pilote IGN à 5 m

Dans l’**Atlas**, depuis la ville historique, choisissez **Activer le pilote IGN 5 m**, puis entrez dans Marseille réelle. Le bouton de retour restaure le relief historique à 25 m. Le changement est interdit dans une cellule de campagne géographique. Un profil neuf utilise le relief historique à 25 m ; un pack déjà installé reste actif. Le propriétaire de cache existant terrain56/58 conserve le pack actif au rechargement ; un import de continuité garde le relief actuellement installé. Les tuiles terrain déjà admises doivent rester compatibles : un raccord refusé laisse le relief et le cache précédents intacts.

Le pilote couvre les **168 cellules, soit 10,5 km² du centre**. Ses nœuds float32 et ses masques sont copiés exactement depuis les tuiles IGN à 5 m préparées, elles-mêmes issues d’un échantillonnage bilinéaire strict des rasters natifs. Cette transformation ne constitue pas un relevé de voirie. Lambert-93, NGF-IGN69 et les inconnues NoData sont conservés. Les trois petits fragments de données sont versionnés : jouer ce pilote ne demande ni cache métropolitain ni outil GIS.

Sol, rendu et occultation terrain utilisent la même grille triangulée de terrain56. Les références documentées de sol IGN des bâtiments sont conservées ; les autres fondations restent des interprétations adaptées au relief. Les positions anciennes sont vérifiées avec le relief installé. L’entrée existante cherche une voie source libre si nécessaire, annonce le déplacement, ou refuse l’entrée sans créer de terrain. Les marches, accès et ouvrages ne sont pas tous certifiés praticables. L’audit porte sur 38 206 fragments et 34 986 objets bâtis distincts ; 14 323 fragments ont une référence IGN de sol, représentant 14 279 références distinctes. Le MNT dépasse la base fixe de plus de 3 cm dans 13 314 fragments. Il dépasse l’égout de 77 fragments correspondant à 77 objets distincts au seuil strictement positif, dont 76 au-delà de 3 cm. Ce conflit de sources est signalé avant activation ; il peut laisser des bâtiments partiellement engloutis. Le pilote ne résout pas ces références en déplaçant arbitrairement les bâtiments.

## Opérations d’Acte III

Depuis **Pause → Archives et continuité → Centre de commandement**, les actions **Tracer** conservent le mode automobile des étapes de conduite au lieu de calculer un trajet piéton. Le bouton de dossier et la console d’objectif utilisent la même définition d’opération v45. Un refus de route explique le besoin de rejoindre un accès existant ; aucun raccord n’est ajouté.

Les nœuds verrouillés, déjà terminés ou hors étape retrouvent leur explication native. Un objectif actif conserve les preuves v74 : présence, portée, visibilité, canal achevé, choix encore valable, rencontre réelle ou transfert en véhicule. Les rencontres, véhicules, récompenses et remises restent sous les propriétaires 32/37/45. Les états de santé et de défaite ne sont pas réinitialisés pour contourner une étape.

Les points chauds automatiques v43 présents sur ces trajets pouvaient rendre une sauvegarde invalide. Le validateur reconnaît maintenant les 31 identités exactes issues de leurs huit définitions, avec leur zone et leur indice. Les ennemis reprennent santé et état de défaite dans le registre de combat existant ; leur rôle de lame est rétabli. La compatibilité de l’ancien butin est bornée aux identités et aux rôles source correspondants. Les identités inventées ou issues des histoires et contrats v43 restent refusées.

## Tir de précision interrompable

Le sniper prépare son tir pendant **1,05 seconde** avec un contact visuel personnel courant. Un coup reçu, une perte de vue ou un état incompatible annulent la préparation en conservant la récupération payée. Une charge abandonnée derrière un obstacle ne provoque plus un tir immédiat à la réacquisition. La radio seule autorise toujours une recherche, sans droit de tir. Le sniper tient sa visée pendant sa préparation ; son déplacement tactique reprend après le tir ou son interruption.

L’avertissement partage les quatre lignes du HUD netrunner existant ; Écho décrit aussi la préparation réelle. Les dégâts, armure, Rempart et facteurs de récupération restent appliqués par leurs propriétaires existants. Les canaux restent temporaires, avec 32 préparations simultanées au maximum ; seul le délai `attackClock` est conservé dans les registres de combat32/33. Boss et ICE conservent leurs systèmes.

## Appuis et virages des véhicules

Dans la campagne géographique, les véhicules terrestres vérifient leur carrosserie orientée le long du mouvement, avec des échantillons distants d’au plus 4 cm de mouvement de corps. Les dimensions, la marge de contact et la mécanique v24/v57 restent celles des véhicules existants.

À chaque échantillon, neuf appuis demandent le sol et la pente locale au terrain actif. Une pente supérieure à **70 %** ou une altitude absente refuse le mouvement. Cela corrige le cas d’une rampe courte masquée par la moyenne des quatre coins. Les contrôles CPU à 30/60/120 Hz utilisent un relief synthétique déclaré ; ils ne constituent pas une mesure de FPS ni une certification des routes réelles. Les bateaux, aéronefs et zones non géographiques conservent leurs règles.

## Vérifier

```sh
node --test --test-concurrency=2 game/tests/v75/*.test.cjs
python3 -m unittest discover -s game/tests/v75 -p 'test_*.py'
python3 lancer.py --verify
```

La QA facultative utilise Playwright et Chromium, sans dépendance pour le jeu. Les scripts de `game/tests/v75/` acceptent `--url`, `--chromium` et `--output` : `browser_smoke.cjs`, `browser_features.cjs`, `browser_missions.cjs`, `browser_mechanics.cjs`, `browser_terrain.cjs`, `browser_sniper.cjs` et `continuity_browser.cjs`. Démarrer le serveur, fournir son URL avec le port choisi et conserver les rapports. Les tests métropolitains nécessitent les données AMP installées ; le smoke qualifie le repli explicite sur le centre. Les exports historiques de continuité utilisent des profils de test neufs. Les fixtures de pose, de combat et d’état sont déclarées dans chaque rapport.

Les suites historiques des lanceurs71–74 doivent employer leurs vrais lanceurs, rejoués en mémoire depuis leurs commits sans modifier les assertions ; le lanceur partagé courant est testé par75. Les 828 tests automatisés et les 101 étapes des sept suites navigateur ont réussi. Les résultats exécutés, empreintes, limites et preuves figurent dans le [rapport de livraison](data/v75/FEATURE_REPORT.json).

Le survol conserve les données des **92 communes et 52 020 cellules AMP** ; la campagne physique reste celle des **168 cellules du centre**. La restitution architecturale intégrale à 1:1 et la traversée physique de toute la métropole restent à réaliser. Façades, largeurs ou ouvrages inconnus restent interprétés. Le cache lourd dépend du snapshot cloud ; sa restauration sur une nouvelle machine reste à vérifier.
