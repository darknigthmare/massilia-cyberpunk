# v0.76 — Histoires, contre-jeu, entrées et audit du bâti

Cette édition prolonge la v0.75 (`d4c60b1`) et l’ambiance cyberpunk méditerranéenne de Massilia. Elle conserve les systèmes du jeu et les sources historiques67–75 gelées. Les références *Syndicate*, *Cyberpunk 2077* et *E.Y.E: Divine Cybermancy* orientent la lisibilité des combats et les opérations.

## Lancer

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Python 3.11+ et un navigateur WebGL 2 suffisent. Après préparation, `python3 game/tools/serve_v76.py --no-browser` sert directement `SOMA_MASSILIA_URBAIN_v0_76.html` et `metropole-viewer-v76.html`. Le lanceur prépare dix-sept builders et contrôle cinq payloads, 27 originaux, dix-sept HTML, quinze rapports et les assets des 168 cellules du centre. La vérification désactive aussi l’écriture de bytecode dans ses sous-processus. Les sources, contenus et empreintes déterminent la validité du reçu de lancement ; les dates seules ne suffisent pas.

## Six histoires et seize contrats

Le contenu v43 utilisait des identifiants d’incidents ou d’équipements comme noms de zones. Dix étapes d’histoire et quatorze contrats visaient ainsi des lieux absents. Les **23 alias distincts** sont maintenant reliés aux zones déclarées par leurs définitions22/23/28/29 : aucun bâtiment, portail ou raccord nouveau n’est créé. Les identités d’histoire et de contrat restent les mêmes.

Les **55 ennemis** de ces histoires et contrats, dont DÉMOS-12, sont reconnus uniquement par leur identité, zone et indice source. Les 31 identités des huit points chauds déjà prises en charge restent compatibles. Santé, armure, état de défaite et butin utilisent combat32 et la sauvegarde37 existants. Le rôle de lame est rétabli ; les anciens objets de butin ne sont admis que pour leur identité et rôle source précis. Les préparations actives ne sont pas sauvegardées ; leur récupération utilise les adaptateurs75/76 et le scalaire `attackClock`.

Les histoires s’acceptent et se remettent à la **console de campagne de Station Zéro, intérieur A**. Les contrats utilisent le **tableau du district**, dans sa zone sociale. Un objectif exige l’objet actuel, la portée et la visibilité ; un combat exige les unités exactes vaincues et traitées par leur propriétaire. Le canal doit réellement s’achever et les choix doivent encore correspondre à l’étape. Un import remplace les racines d’état et invalide les anciens callbacks. Paiement, réputation et conséquences restent chez43, avec une seule remise.

Le marqueur du contrat **Quai muet**, initialement dans une voiture garée, est replacé par les sélecteurs et composants existants dans sa zone. L’audit des seize marqueurs a borné ce correctif à ce seul contrat ; les véhicules restent à leur place. Les anciens exports sans préférence d’onglet45 reçoivent `operations` ; les cinq onglets natifs sont validés et les champs inconnus restent refusés. Un export après ouverture du commandement est ainsi accepté dans un profil neuf.

Ces histoires et contrats se déroulent dans le monde conceptuel d’origine. Leur progression ne certifie pas une traversée physique de Marseille à 1:1. Les opérations d’Acte III45 et leurs preuves74/75 restent conservées.

## Salves lourdes et brume

Les unités lourdes qui utilisent le comportement32 préparent leur salve pendant **0,70 seconde**. Un coup reçu, une perte de vue ou un état incompatible interrompent la préparation en conservant la récupération payée. L’unité tient sa visée pendant l’amorce, puis reprend son déplacement tactique. Les dégâts, armure, facteurs33 et Rempart restent appliqués par leurs propriétaires. Les boss dédiés26/36 et les ICE conservent leurs systèmes ; DÉMOS-12 utilise déjà le comportement lourd32.

L’avertissement partage les quatre lignes du HUD existant avec les snipers et netrunners ; Écho décrit aussi la préparation réelle. La radio seule autorise une recherche, sans droit de tir. Jusqu’à 32 canaux lourds restent temporaires ; aucun nouveau domaine de sauvegarde ou réserve de joueur n’est ajouté.

La capsule native de brume marquait ses robots sans effet de perception. Elle **masque désormais leur vision personnelle pendant le délai existant de dix secondes**. C’est une évolution explicite du contre-jeu, plus forte que l’ancienne description de précision réduite. Stock, rayon d’application et horloge restent ceux de28. Bruits, mémoire et radio permettent toujours de chercher ; aucun volume géographique de fumée supplémentaire n’est simulé. Les raccourcis du Cortex et des consommables existants sont conservés.

## Arrivées à pied sur le pilote 5 m

L’audit natif des 168 cellules a relevé **15 premiers centres de route candidats qui chevauchaient un véhicule original**. Avec le pilote5m actif, une entrée ou restauration à pied doit maintenant être soutenue, libre pour le corps debout60 et hors des carrosseries57 de la cellule et des voisins déjà construits. La reprise du cache emploie la même validation, y compris si le module d’entrée devient disponible après le premier chargement du relief.

Le repli utilise toujours les centres des segments source déjà livrés et annonce le déplacement. Sans position compatible, le propriétaire75 suspend au titre existant. L’audit n’a pas établi de cas justifiant un nouvel échantillonnage intérieur : aucun candidat supplémentaire ou raccord n’est inventé. Les NoData, pentes et coordonnées Lambert-93 restent contrôlés. Les coutures en véhicule55 suivent leur propre validation ; la branche historique25m reste conservée.

## Examiner les conflits bâti / relief

Dans l’**Atlas**, ouvrez **Conflits bâti / relief IGN 5 m**. La liste présente les **77 objets sur 40 cellules**, dont 76 dépassent 3 cm. Recherche par identité OSM, référence IGN ou cellule, filtre sur la cellule sélectionnée et pagination de dix lignes bornent l’affichage.

Chaque fiche distingue sol minimal IGN, hauteur à l’égout, altitude de l’égout et extrema du MNT sous l’emprise. Elle donne les millésimes, précisions déclarées, méthode d’appariement et empreintes de source. **Sélectionner cette cellule** passe par le bouton natif de l’Atlas ; cette action n’ajoute pas de téléportation ou d’accès.

Les champs sont identiques au fichier BD TOPO acquis et un calcul indépendant par intersection de triangles reproduit les extrema. Aucun défaut de contrat source n’a été établi. Les écarts restent documentés : les cotes fixes, le relief et la géométrie ne sont pas déplacés pour les masquer. L’audit concerne la grille du pilote5m ; il ne décrit pas un autre relief importé et ne mesure ni une façade réelle ni la part engloutie d’un bâtiment.

## Vérifier

```sh
node --test --test-concurrency=2 game/tests/v76/*.test.cjs
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s game/tests/v76 -p 'test_*.py'
python3 lancer.py --verify
```

La QA facultative utilise Playwright et Chromium. Les scripts `browser_smoke.cjs`, `browser_features.cjs`, `browser_mechanics.cjs`, `browser_sniper.cjs`, `browser_terrain.cjs`, `browser_missions.cjs` et `continuity_browser.cjs` de `game/tests/v76/` acceptent `--url`, `--chromium` et `--output`. Démarrer le serveur et fournir son URL avec le port retenu. Le script missions accepte aussi `--scope operations` et `--scope production43` ; la validation complète exécute les deux depuis des profils neufs, ou le scope `all` par défaut. Les scripts qualifient leurs poses, dégâts contrôlés et modifications d’état de fixture ; les deux HTML et rapports doivent correspondre aux producteurs présents avant et après chaque scénario. Le supplément `browser_smoke.cjs --fallback-only` qualifie le repli sur le centre avec le seul manifeste AMP rendu indisponible par un serveur de test en lecture seule.

Les exports historiques70/71/73/74/75 utilisent leurs vraies interfaces dans des profils neufs. Les suites des lanceurs71–75 doivent rejouer leurs lanceurs exacts en mémoire depuis leurs commits, avec assertions intactes ; le lanceur courant est testé par76. Les 944 tests automatisés et 144 étapes navigateur finales ont réussi, avec deux suppléments de 12 contrôles qualifiés séparément. Les résultats réellement exécutés et leurs limites figurent dans le [rapport de livraison](data/v76/FEATURE_REPORT.json).

Le survol conserve les données des **92 communes et 52 020 cellules AMP** ; la campagne physique reste limitée aux **168 cellules et 10,5 km² du centre**. La restitution architecturale intégrale à 1:1, les accès de toute la métropole, une campagne humaine continue et les performances sur GPU joueur restent à vérifier. Le cache lourd dépend du snapshot cloud ; sa restauration sur une nouvelle machine n’est pas établie.
