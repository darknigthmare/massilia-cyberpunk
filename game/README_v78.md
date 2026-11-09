# v0.78 — Parcours, actions et monde

Cette édition poursuit la v0.77 publiée et conserve l’ambiance cyberpunk méditerranéenne de Massilia. Les producteurs 66–77 restent gelés.

## Lancer

Python 3.11+ et un navigateur WebGL 2 suffisent pour jouer depuis une copie complète du dépôt.

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Sous Windows, utiliser `LANCER_JEU.cmd`. La préparation du jeu livré ne télécharge pas de données géographiques. Les outils GIS et Node.js restent facultatifs pour jouer. Après préparation, `python3 game/tools/serve_v78.py --no-browser --port 8790` sert la campagne et le survol courants.

## Portée

La campagne physique conserve 168 cellules et 10,5 km² du centre. Le survol indépendant utilise les données installées des 92 communes ; une copie Git seule annonce le centre partiel. Le cache métropolitain lourd reste hors Git. La restitution architecturale complète à 1:1 et la traversée physique de toute la métropole restent à réaliser.

Les changements de parcours des missions du monde conceptuel sont du level design ; ils ne déplacent pas les coordonnées ou les routes réelles. Les formes interprétées restent identifiées comme telles et les inconnues ne deviennent pas des relevés.

## Toitures renseignées dans OSM

Six toitures `pyramidal` disposant de hauteurs explicites restaient plates dans le survol : de petits retraits du contour faisaient échouer la condition de convexité. Un cadre convexe dérivé est maintenant admis si les deux contours complets restent à moins de 1 cm l’un de l’autre. Le profil est découpé sur le domaine source ; les emprises, cours et positions horizontales des murs ne sont pas remplacées par ce cadre.

Les hauteurs totales, hauteurs de toit, `min_height` et bases NGF restent celles du modèle source. Le toit et le haut des murs suivent le profil interprété. La borne de 1 cm est horizontale ; elle n’est ni une précision de relevé ni une borne verticale. Le profil pyramidal et son sommet restent explicitement interprétés dans l’inspecteur **I**. Relief, références IGN, routes et NAV sont conservés.

## Escortes et run Port

L’acheminement des trois escortes45 utilise le graphe routier existant, au lieu d’un trajet pouvant passer par le métro. Le bouton « Tracer » des appels actifs vise la destination de livraison pour les escortes. Le système natif ne possède pas d’état de passager ou de prise en charge distinct : cette édition aligne le guidage sur son objectif existant, sans ajouter un tel mécanisme. La destination GPS personnelle reste protégée pendant les transitions automatiques.

Le run Port arrive désormais dans `corniche-exterior`, rue existante compatible avec les véhicules, au lieu du pont supérieur `corniche-route` sans liaison automobile connue. C’est une adaptation explicite du parcours dans le monde conceptuel ; aucun alias géographique ou raccord réel n’est créé. Les sept autres parcours restent inchangés. Les refus de tracé et de lancement expliquent leur cause.

## Dégagement de chambre

Le dégagement d’une arme enrayée pouvait s’achever après un changement de zone. L’action conserve son propriétaire30, ses 0,9 seconde et son usure native de 0,6 ; elle est annulée si l’arme, la fiche de condition associée, la scène ou la partie deviennent incompatibles, ou lors d’un décès, d’une récupération, de conduite ou de passage cyber. Une pause normale conserve le temps restant.

L’import direct37 réinitialise cette action temporaire. Le transfert groupé64 la refuse lorsqu’elle est active, comme les autres canaux occupés. Munitions, dégâts et domaines de sauvegarde restent chez leurs propriétaires existants.

## Échec d’une couture

Le transfert métrique55 disposait d’un rollback incomplet : une erreur pouvait laisser une voiture dans les deux cellules avec les coordonnées de destination, ou conserver le verrou lorsque le snapshot initial échouait. La correction vise la cohérence de la scène physique et la libération du verrou. Les tests injectent explicitement des fautes aux frontières du propriétaire ; ils ne décrivent pas un trajet ayant naturellement provoqué une panne.

La compensation persistante utilise les propriétaires natifs et reste limitée par une éventuelle erreur durable de stockage. Elle ne constitue pas une annulation globale des visites, découvertes et récompenses gérées par les autres systèmes.

## Validation

Lire [AGENTS.md](../AGENTS.md), les propriétaires des systèmes et [VALIDATION.md](../docs/development/VALIDATION.md). Les résultats propres à cette édition sont consignés dans [FEATURE_REPORT.json](data/v78/FEATURE_REPORT.json) : **1 155 tests réussis** (725 JavaScript et 430 Python), sans échec ni saut dans les résultats finaux. Les **29 étapes navigateur** sur trois profils neufs (18 campagne, 7 survol, 4 monde ; 27 noms distincts) sont liées aux sources et scripts réels. Les quatre fichiers HTML/rapports testés sont exactement retrouvés par la préparation complète ; aucun ancien PASS n’est substitué à une exécution courante.

Les 21 builders sont reconstruits puis vérifiés. Les 160 sources parentes et 36 livrables hérités restent identiques. La vérification n’a modifié aucun des 917 fichiers surveillés ni des 148 fichiers de bytecode. Une copie isolée de 216 fichiers, sans Git ni cache world/AMP copié, vérifie 5 payloads et 27 originaux puis régénère 168 cellules/673 fichiers par le bootstrap stdlib avec les imports GIS bloqués. Les 196 entrées transitives et les deux HTML/deux rapports78 sont identiques au canonique. Le lancement HTTP depuis le reçu vérifié sert les deux HTML sans relancer de builder.

```sh
node --test game/tests/v78/*.test.cjs
python3 -B -m unittest discover -s game/tests/v78 -p 'test_*.py'
```

Les 60 cas Python de la v0.78 ont été exécutés par sous-suites (44 infrastructure et 16 fonctionnalités). Les suites historiques 71–77 utilisent leurs lanceurs exacts en mémoire, avec les références Git indiquées dans le rapport. Node 24.19.0 et Python 3.12.14 sont les versions exécutées ; le jeu conserve son minimum documenté Python 3.11+.

Les drivers facultatifs `browser_gameplay.cjs`, `browser_viewer.cjs` et `browser_world.cjs` partagent les options `--url`, `--chromium` et `--output`. Les profils de test sont jetables, les poses/ressources/états préparés déclarés. La couture positive utilise un taxi source et un portail vérifié avec pose préparée ; elle ne constitue pas une conduite continue. Les fautes de rollback sont des tests du contrat natif55/58, distincts du navigateur normal.

Captures : Playwright 1.62.1 / Chromium 154 / SwiftShader,1280 × 720. Elles ne mesurent pas un GPU joueur et ne constituent pas une campagne humaine. Le repli navigateur sans cache AMP n’est pas rejoué dans cette édition ; sa reconstruction stdlib l’est. Les preuves et diagnostics intermédiaires restent hors Git sous `/workspace/massilia-geodata-generated/validation-v78-2026-11-09`. La restauration dans une nouvelle machine cloud n’est pas indépendamment vérifiée.
