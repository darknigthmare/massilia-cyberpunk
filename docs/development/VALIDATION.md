# Validation de Massilia Cyberpunk

## Référence et portée

Ce guide décrit les vérifications de **SOMA//MASSILIA v0.72**, à partir du commit
[`e1b292a01b720e54d194d9e6f2a4d4b39581b9e8`](https://github.com/darknigthmare/massilia-cyberpunk/tree/e1b292a01b720e54d194d9e6f2a4d4b39581b9e8).
Il constitue une procédure ; les résultats restent ceux du rapport associé à chaque révision.
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
Le contrôle courant est `game/tests/v72/browser_smoke.cjs`, décrit ci-dessous.
Une réussite du script historique ne prouve pas une validation navigateur v72.

## Smoke navigateur courant : campagne et survol v72

Le [smoke v72](../../game/tests/v72/browser_smoke.cjs) utilise Playwright pour Node.js.
**Playwright 1.56.1** est la version utilisée lors de la première exécution de ce contrôle.
C'est une dépendance facultative de QA : le jeu reste jouable avec Python et un navigateur,
sans Node.js ni Playwright. La présence du script ne constitue pas une preuve de réussite ;
conserver son rapport d'exécution et le commit auquel il se rapporte.

Pour installer cette dépendance de QA à la racine, sans modifier un manifeste du jeu :

```sh
npm install --no-save --package-lock=false playwright@1.56.1
```

Après la préparation complète décrite plus haut, démarrer le serveur dans un terminal :

```sh
python3 game/tools/serve_v72.py --no-browser --port 8765
```

Dans un second terminal, fournir le chemin d'un exécutable Chromium existant.
Remplacer `/chemin/vers/chromium` dans cette commande ; ajuster le port si nécessaire :

```sh
node game/tests/v72/browser_smoke.cjs \
  --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_72.html \
  --chromium /chemin/vers/chromium \
  --output test-results/v72
```

Pour utiliser le Chromium géré par Playwright, exécuter `npx playwright install chromium`,
puis omettre l'option `--chromium`. Le script utilise un contexte navigateur neuf et isolé,
sans profil habituel, sauvegarde utilisateur, interception réseau ni remplacement des API du jeu.
`--timeout` règle le délai maximal de chaque étape, en millisecondes ; sa valeur par défaut
est `90000`. Les dépendances locales `/node_modules/` et les sorties `/test-results/`
sont ignorées par Git.

Le scénario exerce les points d'entrée et propriétaires réels :

1. Charger l'édition v72, entrer par **Explorer Marseille réelle** et vérifier la scène,
   les empreintes du socle et la compilation du programme WebGL2.
2. Ouvrir le Cortex avec **Maj+F1**, fermer son panneau, puis activer le **Rempart** par
   son bouton. Les compteurs, délais et la protection temporaire deviennent non nuls.
3. Exporter la copie groupée, changer temporairement les crédits de 17, puis réimporter
   avec l'importeur réel. Vérifier les valeurs restaurées et l'annulation de la protection.
4. Recharger la page, contrôler la continuité, ouvrir le survol avec son bouton v72,
   puis exercer les inspecteurs bâtiment et voirie sur la scène réellement chargée.
5. Comparer le stockage durant le survol et revenir au jeu par son lien de retour.
   Vérifier à nouveau les données persistantes et collecter les erreurs d'exécution.

Le script fige temporairement la simulation avec `paused=true` pour comparer les délais
sans temps de jeu écoulé. Cette instrumentation et la mutation des crédits figurent dans
le rapport. Aucune scène de combat ni entité ennemie artificielle n'est injectée.

Le répertoire de sortie contient `report.json`, les captures PNG et `grouped-save-v72.json`,
copie de la partie fraîche du contrôle. Le rapport distingue les étapes réussies et échouées,
les observations, les interventions du test, les limites et les erreurs JavaScript, console,
HTTP ou réseau. Un échec produit un code de sortie non nul et, si possible, une capture
supplémentaire ; conserver ce résultat pour diagnostiquer le problème.

Un **HTTP 404 du seul manifeste métropolitain facultatif** est attendu uniquement si
le repli sur le centre est ensuite réellement rendu et correctement annoncé.
L'annulation du corps de cette même réponse peut produire `net::ERR_ABORTED` : elle n'est
acceptée qu'avec la même URL de manifeste, un fetch 404 journalisé à la même étape et
le repli observé. Le rapport la distingue des ressources annulées pendant une navigation.
Les autres erreurs restent des échecs ; aucun échec réseau générique n'est masqué.

### Portée de ce contrôle

- Le domaine persistant `v70` partagé avec la v71 est vérifié dans le jeu v72.
  Les anciennes pages et copies de sauvegarde v70/v71 restent à exercer séparément.
- Une protection Cortex active est réellement nettoyée lors de l'import. Les contacts
  radio et préparations netrunner sont contrôlés vides après restauration ; leur remise
  à zéro depuis un combat réel actif reste à observer.
- Un inspecteur peut retourner « vide », « occulté » ou « budget atteint » ; son résultat
  est conservé explicitement. L'ouverture du panneau ne prouve pas la sélection d'un objet.
- Le contrôle observe le manifeste installé et une première scène chargée. Les 92 destinations
  administratives ne prouvent pas que le cache métropolitain complet est présent ou parcouru.
- Le rendu headless demande SwiftShader. Il ne mesure pas les performances d'un GPU joueur,
  ne valide pas un long parcours physique et ne certifie aucune restitution à 1:1.

## Smoke navigateur du HUD v72

Le [smoke HUD](../../game/tests/v72/hud_browser_smoke.cjs) reprend les prérequis Playwright,
le serveur `serve_v72.py` et les options du smoke précédent. Il utilise son propre contexte
navigateur isolé et un répertoire de sortie distinct :

```sh
node game/tests/v72/hud_browser_smoke.cjs \
  --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_72.html \
  --chromium /chemin/vers/chromium \
  --output test-results/v72-hud
```

Après l'entrée réelle dans Marseille, le scénario mesure **19 panneaux** à **1920 × 1080**,
**1440 × 1000**, **1280 × 720** et **1024 × 768**, puis revient à 1440 × 1000.
Il contrôle leurs nœuds conservés pendant les transitions, leur visibilité, leur présence
dans les huit zones, leurs limites dans la fenêtre, les intersections et le débordement
horizontal, avec une tolérance de 1 pixel CSS.

Le Cortex est ouvert par **Maj+F1**, puis par **Tab → Augmentations actives**.
Ses redimensionnements couvrent les mêmes tailles et **700 × 800 pour le menu uniquement**.
Le contrôle vérifie le masquage du sous-arbre HUD, le défilement et le clic réel de fermeture.
Pendant les pauses créées par les menus, il compare seulement crédits, zone, `core.v70`
et énergie du cyberdeck. Il n'active aucune capacité et n'écrit pas dans l'état du jeu.

La sortie contient `report.json`, les mesures, les versions du navigateur et de Playwright,
les erreurs collectées et les captures HUD à 1280/1024 ainsi que Cortex à 700 pixels de large.
Une capture d'échec est tentée si nécessaire. Conserver le rapport avec la révision testée ;
la commande documentée ne constitue pas un résultat d'exécution.

La navigation complète au clavier, le jeu mobile, les situations de combat et les panneaux
conditionnels de poursuite ou de conduite ne sont pas qualifiés par ce scénario.
Le réglage « grands textes » existant concerne le dialogue ; il n'est pas traité comme
un réglage de taille du HUD. Voir le [dossier du HUD v72](HUD_V72.md) pour le changement
de disposition et ses preuves propres.

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

- Importer de véritables copies de sauvegarde v70/v71 dans l'édition courante et documenter
  les valeurs conservées, migrations éventuelles et erreurs de compatibilité.
- Observer en combat réel la radio, ses expirations et le netrunner interrompu, notamment
  lors d'une pause, d'un import ou d'un changement de zone.
- Rejouer les trajets AMP sur un cache identifié, en publiant couverture et tests sautés.
- Mesurer un parcours de transitions sur plusieurs configurations graphiques identifiées.
- Vérifier la lisibilité du Cortex, des télégraphes et des inspecteurs avec les options d'affichage.

Ces éléments sont des validations à réaliser ; ils ne désignent pas des défauts reproduits
et n'annoncent aucune fonctionnalité ajoutée par cette documentation.
