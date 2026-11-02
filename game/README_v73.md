# v0.73 — Écho tactique, détours guidés et toitures sourcées

Cette édition poursuit la fidélité urbaine et les systèmes tactiques de Massilia. Les références *Syndicate*, *Cyberpunk 2077* et *E.Y.E: Divine Cybermancy* orientent les choix de lisibilité, d’intrusion et de contre-jeu, avec les systèmes et ressources propres au projet.

## Lancer cette édition

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Python 3.11+ et un navigateur WebGL 2 suffisent. Après préparation, `python3 game/tools/serve_v73.py --no-browser` sert directement `SOMA_MASSILIA_URBAIN_v0_73.html` et `metropole-viewer-v73.html`. Les lancements suivants contrôlent les sources, les cinq parties du payload, les 27 originaux, onze HTML, neuf rapports et les assets des 168 cellules du centre avant de réutiliser le reçu local. Les dates de modification seules ne font pas foi.

La v0.73 dérive de la v0.72 fusionnée sur `main` au commit `3ce16c3`, avec ses corrections de couverture NAV et son HUD réorganisé. Les sources 67–72 sont conservées et leurs empreintes contrôlées ; les constructions ne dépendent pas de Git ou des outils GIS.

## Écho dans la rue

**Maj+F2** active toujours **Écho de trame**, pendant cinq secondes et à 24 m dans le plan local, depuis le cyberdeck v42. Le coût de 12 unités, la récupération de 12 secondes, la tension et les compteurs restent ceux du propriétaire v70. **Maj+F1** ouvre le Cortex ; **Maj+F3/F4** et les consommables **F1–F4** conservent leurs commandes.

Le scan vérifie désormais le corps dans le véritable champ de caméra et sa ligne de vue. En secteur géographique, sa hauteur utilise le terrain NGF ; les offsets d’animation des unités ne sont pas pris pour des altitudes absolues. Les unités derrière un obstacle, hors champ ou sans hauteur exploitable ne produisent pas de fiche.

Les fiches donnent rôle, intégrité et conseil tactique. Au plus huit unités sont retenues sur 128 candidates examinées et quatre repères sont affichés. Une perte de visibilité les retire ; ces fiches ne constituent pas un suivi à travers les murs. Pause, onglet masqué, décès, conduite, import et remplacement de zone ou d’état effacent les présentations temporaires.

L’objectif narratif rejoint la colonne de navigation afin de conserver santé, armure et munitions dans la fenêtre pendant le combat aux résolutions contrôlées de 1024 × 768 et 1280 × 720. Les panneaux et leurs propriétaires restent conservés.

Aucune nouvelle réserve d’énergie ou clé `core.v73` n’est ajoutée. La continuité reste celle de `core.v70`, et les effets temporaires ne sont pas sérialisés.

## Guider un corridor routier

Le survol propose **« Guider le corridor par ici »**, avec des coordonnées Lambert-93 facultatives. Le guide infléchit la sélection des cellules vers un détour : il ne crée aucun raccord et n’impose pas une étape au trajet calculé.

1. Ouvrir **Itinéraire local** et marquer le départ.
2. Voler près du détour souhaité, rouvrir le panneau et choisir **Guider le corridor par ici**.
3. Voler à l’arrivée, rouvrir et analyser. Si nécessaire, demander explicitement l’élargissement.
4. **Retirer le guide** rétablit le corridor direct. Une nouvelle origine ou l’exemple intégré efface aussi le guide précédent.

Les deux jambes du corridor sont réservées avant les cellules latérales. Les budgets restent 96 cellules puis 192, 24 000/48 000 nœuds, 32 000/64 000 arêtes, 128 Mio comptabilisés et six secondes par analyse. Un corridor trop long est refusé avant les lectures si sa couverture minimale dépasse déjà ces limites. Les lectures globales restent bornées à deux, dont une seule lecture NAV sous verrou de scène.

Trois échecs du corridor direct élargi deviennent des trajets source de **5 138,14 m**, **7 341,71 m** et **9 196,51 m**, sur 75, 108 et 107 cellules respectivement, avec les mêmes budgets. Ces exemples ne garantissent pas un résultat pour toute paire de points.

Les graphes conservent leurs identités OSM, accès, sens uniques, escaliers et restrictions de tour, avec le noyau63 vérifié. Un guide ne transforme pas deux axes qui se croisent en jonction. Un secteur sans préparation NAV reste manquant ; une absence de trajet dans les cellules chargées ne prouve pas une déconnexion de la métropole. Les rubans 3D restent découpés contre le MNT complet déjà rendu.

## Toitures : exploiter les dimensions disponibles

Certains bâtiments disposent de `height`, `roof:height` et d’un type `gabled` ou `hipped`, mais leur emprise légèrement rentrante empêchait tout toit paramétrique. La v0.73 accepte un cadre rectangulaire dérivé lorsque l’emprise extérieure complète s’en écarte d’au plus 1 % en aire. Les hauteurs restent explicites ; le sens du faîtage conserve les règles source et les refus de conflits existants.

Le cadre sert au profil du toit. Les triangles préparés, trous de cour, retraits, murs et limites de cellule gardent leur emprise réelle. La vérification sur douze cellules réelles et 36 assets contrôlés confirme **huit nouveaux modèles** parmi 38 bâtiments disposant de paramètres de toiture : dix étaient déjà représentés, dix-huit le sont maintenant. Les autres bâtiments et surfaces de ces cellules restent identiques. Le cache géographique n’est pas réécrit. Les paramètres de faîtage et de pente restent **interprétés**, avec leur provenance consultable dans l’inspecteur architectural **I** ; ils ne constituent pas un relevé architectural. Les bases d’altitude héritées des corps et de leurs parties restent inchangées ; un pan peut être partiellement masqué par un autre volume. Leur réconciliation reste à vérifier avec des références architecturales suffisantes.

## Vérifier

```sh
MASSILIA_ROUTE_WORLD=/chemin/vers/manifest.json node --test --test-concurrency=2 game/tests/v73/*.test.cjs
python3 -m unittest discover -s game/tests/v73 -p 'test_*.py'
python3 -B -S lancer.py --verify
node game/tests/v73/browser_smoke.cjs --chromium /chemin/vers/chromium --output test-results/v73
node game/tests/v73/browser_features.cjs --chromium /chemin/vers/chromium --output test-results/v73-features
node game/tests/v73/continuity_browser.cjs --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_73.html --chromium /chemin/vers/chromium --output test-results/v73-continuity
```

Les essais navigateur utilisent Playwright facultatif pour la QA ; le jeu n’en dépend pas. `browser_features.cjs` exige le cache métropolitain AMP installé pour son trajet réel et ses sélections de toits : ce contrôle d’intégration ne qualifie pas une copie Git sans ce cache. Le smoke principal accepte le repli sur le centre, à condition de le voir réellement rendu et annoncé. Les profils sont jetables. Les essais ont été exécutés sur Chromium 154 avec SwiftShader et Playwright 1.62.1 ; ils ne mesurent pas les performances d’un GPU joueur. Les rapports distinguent scènes réelles, instrumentation et fixtures. Pour les contrôles hérités, conserver le corpus 67–72 ; les tests de lanceur71/72 visent leurs vraies commandes historiques, et le lanceur actuel est testé dans v73. Le [rapport de livraison](data/v73/FEATURE_REPORT.json) indique les tests et observations effectivement réalisés.

Le cache installé conserve 92 communes, 52 020 cellules et le MNT IGN à 5 m. La campagne physique reste limitée à 168 cellules du centre, soit 10,5 km². La restitution architecturale intégrale à 1:1 et la traversée physique de toute la métropole restent inachevées ; les données sans mesure suffisante demeurent identifiées comme interprétées.
