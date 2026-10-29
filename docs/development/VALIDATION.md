# Validation de Massilia Cyberpunk

## Référence et portée

Ce guide décrit les vérifications de **SOMA//MASSILIA v0.72**, à partir du commit
[`e1b292a01b720e54d194d9e6f2a4d4b39581b9e8`](https://github.com/darknigthmare/massilia-cyberpunk/tree/e1b292a01b720e54d194d9e6f2a4d4b39581b9e8).
Il constitue une procédure ; il ne rapporte aucune nouvelle exécution de tests.
Consigner le commit réellement vérifié, les commandes, les résultats et les limites.

Une réussite des contrôles de code ne certifie ni une campagne humaine complète,
ni le rendu sur tous les GPU, ni une restitution architecturale intégrale à 1:1.
La campagne physique du centre et le survol métropolitain ont des périmètres distincts.

## Prérequis

- Python **3.11 ou plus récent** pour la préparation et les contrôles Python.
- Node.js **18 ou plus récent**, selon le README du dépôt, pour les tests JavaScript.
  Ce minimum documenté n'est pas une affirmation de validation sur Node.js 18.
- Un navigateur compatible **WebGL 2** pour la validation du jeu et du survol.
- Une copie complète du dépôt, comprenant `game/`, `payload/` et `lancer.py`.
- Au moins 1 Go libre en plus du dépôt pour les sorties et fichiers temporaires ;
  les jeux de données métropolitains peuvent nécessiter davantage d'espace.

Les commandes suivantes partent de la racine du dépôt. Sous Windows, remplacer
`python3` par la commande du Python installé et utiliser un shell développant les
motifs `*.test.cjs`, ou fournir explicitement les fichiers correspondants.

## Préparer une copie complète

Avant toute modification, relever `git rev-parse HEAD` et `git status --short`.
Conserver les modifications existantes et identifier la version réellement ciblée.

```sh
python3 --version
node --version
python3 lancer.py --prepare-only
python3 lancer.py --verify
```

Le lanceur restaure les fichiers volumineux inclus, contrôle les 27 originaux,
puis reconstruit les éditions et survols successifs jusqu'à v0.72.
La préparation de la livraison incluse ne nécessite pas d'acquisition géographique.
Un refus d'empreinte doit être diagnostiqué : ne pas remplacer une empreinte attendue
pour accepter un fichier altéré, ni supprimer les changements de l'utilisateur.

Les sources historiques sont gelées par les builders, notamment
`game/build_v72.py` avec `FROZEN_PARENT_SOURCES` et `PARENT_SHA256`.
Modifier un parent gelé peut invalider toute la chaîne de reconstruction.
Effectuer les changements dans l'extension appropriée ou une nouvelle édition,
en conservant les contrats de reconstruction et de continuité.

## Contrôles existants

Le contrôle JavaScript global documenté est :

```sh
node --test --test-concurrency=2 game/tests/v67/core.test.cjs game/tests/v68/*.test.cjs game/tests/v69/*.test.cjs game/tests/v70/*.test.cjs game/tests/v71/*.test.cjs game/tests/v72/*.test.cjs
```

Les contrôles Python documentés pour le lanceur courant et ses extensions sont :

```sh
python3 -m unittest discover -s game/tests/v70 -p 'test_*.py'
python3 -m unittest discover -s game/tests/v72 -p 'test_*.py'
python3 -S lancer.py --verify
```

Pour un changement circonscrit, commencer par la suite correspondante :

| Sujet | Commande ciblée depuis la racine |
| --- | --- |
| Radio et préparation netrunner | `node --test game/tests/v72/contact-sharing.test.cjs game/tests/v72/netrunner-integration.test.cjs` |
| Voirie et inspection | `node --test game/tests/v72/fidelity.test.cjs` |
| Corridors et conformité du routage | `node --test game/tests/v72/route-corridor.test.cjs game/tests/v72/route-conformance.test.cjs` |
| Reconstruction v72 | `python3 -m unittest discover -s game/tests/v72 -p 'test_build_v72.py'` |
| Cache du lanceur courant | `python3 -m unittest discover -s game/tests/v72 -p 'test_launch_cache_v72.py'` |

Élargir ensuite les contrôles selon les dépendances touchées et le risque restant.
Un changement uniquement documentaire n'exige pas de nouveaux tests de gameplay.

## Interpréter les résultats

Relever séparément réussites, échecs et tests sautés. Conserver les motifs de saut.
`test_build_v72.py` saute des contrôles d'intégration si le HTML parent v71 est absent :
une copie contenant seulement les petits fichiers source ne suffit pas à tout vérifier.

Les tests sur les vrais graphes AMP nécessitent `MASSILIA_ROUTE_WORLD` pointant vers
le manifeste du monde effectivement préparé. Sans cette variable, le cas réel concerné
est sauté. Les fixtures et la conformité historique restent utiles, mais ne prouvent
pas à elles seules le routage sur les données métropolitaines installées.

Le cache métropolitain complet est hors Git. Une copie source seule peut afficher
le centre partiel ; noter le manifeste, l'édition et la couverture effectivement utilisés.
Un itinéraire calculé ne certifie pas la traversabilité physique de la métropole.

Les anciens tests Python du lanceur v71 visent leur commande historique ; les tests
v72 vérifient le lanceur partagé actuel. Ne pas affaiblir leurs assertions pour les mélanger.

Le smoke test `game/tests/v68/browser_smoke.py` accepte seulement les versions
`0.68` et `0.69`. Il nécessite Playwright/Chromium et reste un contrôle historique.
Ne pas annoncer une validation navigateur v72 à partir de ce script sans adaptation
explicite, scénarios actuels et preuve d'exécution sur l'édition v72.

## Parcours manuel de la v0.72

Lancer `python3 lancer.py --no-browser`, puis ouvrir l'adresse fournie par le serveur.
Après préparation, `python3 game/tools/serve_v72.py --no-browser` sert aussi cette édition.
Utiliser un profil navigateur de test séparé et une sauvegarde de test exportée ;
ne pas effacer ou importer par-dessus la sauvegarde habituelle du joueur.

1. Vérifier le titre v0.72, le chargement initial et l'entrée dans la campagne.
   Relever erreurs console, erreurs WebGL et ressources manquantes.
2. Ouvrir le Cortex avec **Maj+F1**, exercer les capacités disponibles et vérifier
   leurs coûts, délais et charge neurale. Confirmer que **F1–F4** gardent les consommables.
3. Observer une acquisition visuelle, une perte de contact et une réception radio.
   Vérifier la recherche à la dernière position connue, son expiration et l'absence
   de tir ou d'arrestation permis par la seule radio derrière un obstacle.
4. Déclencher une préparation netrunner, l'interrompre par un impact ou une perte
   de ligne de vue, puis vérifier la récupération et la lisibilité du télégraphe.
5. Exercer pause, reprise, changement de cellule, décès ou récupération lorsqu'ils
   sont accessibles au scénario. Rechercher les actions ou contacts temporaires résiduels.
6. Exporter, recharger puis importer la sauvegarde de test ; contrôler progression,
   compteurs et délais persistants, ainsi que l'annulation des protections temporaires.
7. Ouvrir le survol ; vérifier la couverture annoncée, les inspecteurs bâtiment **I**
   et voirie **J**, les surfaces occultantes, puis le retour au jeu sans perte de sauvegarde.
8. Traverser plusieurs limites de cellules ; essayer un itinéraire, son élargissement
   explicite et son effacement. Distinguer données absentes, budget atteint et absence
   de trajet dans le corridor ; ne pas combler visuellement les secteurs de relief absents.

## Mesures de performances comparables

Identifier les commits de référence et de modification, puis utiliser les mêmes trajet,
navigateur, GPU, résolution, réglages et état de cache pour comparer avant/après.
Séparer les mesures à froid et à chaud.
Relever temps de chargement, temps de frame et pics aux transitions, mémoire suivie,
lectures en attente, géométries résidentes et erreurs. Répéter le parcours pour repérer
une accumulation après aller-retour, annulation de chargement ou changement de monde.
Une hausse de FPS seule ne justifie pas une perte de géométrie, de données ou d'IA.
Les budgets existants et la libération des ressources restent des critères de contrôle.

## Prochaines validations à réaliser

- Établir un smoke navigateur dédié à v72 couvrant campagne et survol avec preuves visuelles.
- Exercer les sauvegardes de test v70/v71 dans l'édition courante et documenter la continuité.
- Rejouer les trajets AMP sur un cache identifié, en publiant couverture et tests sautés.
- Mesurer un parcours de transitions sur plusieurs configurations graphiques identifiées.
- Vérifier la lisibilité du Cortex, des télégraphes et des inspecteurs avec les options d'affichage.

Ces éléments sont des validations à réaliser ; ils ne désignent pas des défauts reproduits
et n'annoncent aucune fonctionnalité ajoutée par cette documentation.
