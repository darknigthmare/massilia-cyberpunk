# v0.70 — Cortex tactique et navigation locale

La v0.70 poursuit les chantiers de Massilia avec des mécaniques tactiques utilisables dans la campagne existante et une analyse des axes routiers dans le survol. Le jeu contient déjà armes, armure, dégâts localisés, hacks, puces, talents, récits, factions, compagnons et véhicules : cette couche améliore leur cohérence et ajoute des capacités actives.

| Référence demandée | Direction retenue dans Massilia |
| --- | --- |
| Syndicate, PS3 | Intrusion ciblée, lecture tactique des machines, capacités actives à coût réel et contre-mesures. |
| Cyberpunk 2077, PS5 | Choix d’implant, gestion du cyberdeck et de la tension, usage de la ville et des déplacements. |
| E.Y.E: Divine Cybermancy, Steam | Ressources neurales, risque et combinaison de compétences, d’équipement et d’infiltration. |

## Lancement

Depuis la racine du dépôt :

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Le lanceur choisit `SOMA_MASSILIA_URBAIN_v0_70.html`. Les 27 fichiers originaux, la baseline, le PBF et les sources v0.69 restent vérifiés. La reconstruction utilise uniquement Python standard ; les outils GIS restent facultatifs. Le survol v70 est `metropole-viewer-v70.html` ; son retour ouvre la campagne v70.

Après préparation, `python3 game/tools/serve_v70.py --no-browser` démarre directement le serveur sans reconstruire les éditions précédentes.

## Augmentations actives

**Maj+F1** ouvre le Cortex tactique et ses commandes. Le bouton **« Augmentations actives »** du Cortex permet aussi d’y accéder à la souris ou au toucher. Les touches F1–F4 sans Maj continuent à utiliser les consommables existants.

| Action | Raccourci | Énergie | Effet | Durée | Récupération |
| --- | --- | ---: | --- | ---: | ---: |
| Écho de trame | Maj+F2 | 12 | Lecture des unités visibles à portée, en respectant les obstacles. | 5 s | 12 s |
| Rempart cortical | Maj+F3 | 28 | Réduction de 55 % des impacts de combat, budget de 40 points absorbés. | 4 s | 24 s |
| Ancrage réflexe | Maj+F4 | 24 | Réduction de 35 % du recul de visée réel. | 5 s | 20 s |

Les capacités utilisent **le cyberdeck urbain v42 existant**, dont la régénération et les quickhacks restent actifs. La charge neurale est un indicateur de risque, pas une seconde réserve d’énergie. Elle augmente la tension à l’activation et se dissipe au temps de jeu. Pause, décès, conduite, plongée et canal en cours sont traités explicitement. Un refus ne coûte rien. Ancrage est refusé lorsque le réglage « Mouvement réduit » neutralise déjà le recul de visée.

Rempart et Ancrage bloquent temporairement le lancement d’une nouvelle intrusion. Écho peut rester actif pendant un hack engagé ensuite. Les capacités ne changent ni dégâts sortants, ni portée des armes, ni vitesse globale du temps. Rempart réduit les impacts des unités tactiques, des boss, des policiers et des anciennes sentinelles, après les multiplicateurs de défense et avant l’armure. Ces voies partagent un seul budget de 40 points d’impact absorbés ; ce montant n’est pas une promesse de 40 PV supplémentaires. Les gardes de récupération, les conséquences des arrestations et les dégâts corporels associés restent appliqués. Les événements neuraux et environnementaux conservent leurs règles propres.

## Infiltration et intrusion

La posture canonique réunit C, Ctrl et les obligations de hauteur libre. Les événements de pas utilisent la distance réellement parcourue, même si la restitution sonore est désactivée. Les tirs ne sont émis qu’après un vrai tir accepté et restent localisés au point d’émission.

Les unités tactiques gardent le dernier contact effectivement vu ou entendu. Quand le joueur passe derrière un obstacle, leur recherche et leur choix de couvert utilisent cette mémoire au lieu de la caméra actuelle. Une alerte d’escouade dépourvue de position ne crée pas de cible fictive. Les contacts des caméras transmettent une position réellement vue, sans raviver indéfiniment une ancienne mémoire. Les poursuites des anciennes IA de police et de sécurité restent un chantier distinct.

Les trois quickhacks urbains existants gardent leur énergie, canaux et effets : aveuglement optique électronique, immobilisation et interruption de l’arme. Ils n’effacent pas la mémoire d’alerte. Le panneau propose ces programmes sur la machine visée. Les transferts groupés et voyages consultent maintenant le véritable état de canal v42.

## Itinéraires dans le survol

Le panneau **« Itinéraire local »** analyse les graphes préparés en mode marche ou voiture. Marquez le départ à votre position, reprenez le survol jusqu’à l’arrivée, puis rouvrez le panneau pour analyser le trajet vers cette position. Les coordonnées précises Lambert-93 restent disponibles dans un volet facultatif. Le résultat présente les projections sur les axes, la longueur et un tracé 2D. L’exemple Belsunce → République utilise environ 599,49 m d’axes sur 15 secteurs.

Les graphes sont chargés uniquement à la demande et vérifiés par empreintes, source, cellules et moteur. La recherche réutilise le noyau historique v63. Les limites par défaut sont 36 secteurs, 12 000 nœuds, 16 000 arêtes, 64 Mio comptabilisés et un budget de temps de 3 s. Les zones analysées peuvent donc rester partielles. Les approches libres depuis les points saisis ne deviennent pas des segments routiers inventés.

Le panneau fige l’image 3D et emprunte le créneau de chargement une fois la scène stabilisée. La fermeture annule les lectures, attend leur fin, puis rétablit le survol. Le plafond global reste de deux requêtes d’assets. Une annulation, une interruption ou un dépassement de budget reçoit son propre statut.

Cette analyse ne certifie ni passage au sol, ni accès privé, ni ouvrages sans altitude. Elle n’active pas la navigation physique ou une migration de campagne.

## Géographie et rendu

Le cache métropolitain préparé reste celui de la v0.69 : **52 020 secteurs, 92 communes**, relief IGN à 5 m, 299 391 références à l’égout et 51 809 graphes routiers. La campagne conserve ses **168 cellules du centre**. Les données lourdes et l’archive portable restent hors Git ; voir [README_v69.md](README_v69.md) et [README_world_bundle.md](tools/metropole/README_world_bundle.md).

Les nouveaux matériaux interprètent des tags explicites jusque-là non affichés : façade en verre, plastique, toiture végétalisée ou gravillonnée et couleur CSS aqua. Les couleurs déclarées gardent la priorité. L’audit réel concerne 102 bâtiments uniques (94 façades et 9 toits, avec recouvrement), sans modifier les géométries, dimensions ou altitudes. Une couleur issue d’un matériau reste une palette interprétée, pas une texture ou façade relevée.

L’audit des autres formes de toit ne trouve pas de nouvelle cohorte possédant les paramètres de hauteur nécessaires. Les formes insuffisamment documentées restent approximatives. La restitution architecturale 1:1 complète reste un chantier ouvert.

## Continuité et validation

La continuité conserve son format strict v37, avec un domaine **optionnel `core.v70`** explicitement validé. Il contient sélection, délais, charge neurale et compteurs ; les buffs et le budget actif de Rempart n’y sont jamais enregistrés. Les sauvegardes antérieures sans ce domaine restent acceptées. À l’import ou au rechargement, les effets temporaires cessent et les délais enregistrés sont conservés. Les éditions antérieures ne comprennent pas ce nouveau domaine : conserver leurs copies d’origine pour les utiliser avec ces éditions.

```sh
node --test --test-concurrency=2 game/tests/v67/core.test.cjs game/tests/v68/*.test.cjs game/tests/v69/*.test.cjs game/tests/v70/*.test.cjs
python3 -m unittest discover -s game/tests/v70 -p 'test_*.py'
python3 lancer.py --verify
```

Les tests route peuvent exercer le cache réel en définissant `MASSILIA_ROUTE_WORLD` vers son manifeste. Les contrôles GIS v0.69 restent documentés dans son guide. Les preuves de jeu et de survol doivent utiliser les HTML générés effectivement testés ; une validation logicielle ne constitue pas un relevé de Marseille ni une équivalence de contenu ou de rendu avec les jeux de référence.

Le [rapport de livraison v0.70](data/v70/FEATURE_REPORT.json) consigne les empreintes finales, les 725 tests réussis et les emplacements des preuves de jeu. Les données et captures volumineuses restent dans l’espace de développement hors Git.
