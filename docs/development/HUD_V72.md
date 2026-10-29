# HUD v0.72 — panneaux réorganisés et continuité vérifiée

## Résultat et référence

Le 29 octobre 2026, les panneaux de campagne qui se superposaient ont été
réorganisés dans une grille commune. Le contrôle navigateur du HUD réussit
**19 étapes sur 19** ; le parcours de sauvegarde et de survol rejoué sur cette
nouvelle campagne réussit **11 étapes sur 11**. Ces résultats portent sur les
formats, les composants et la scène décrits ci-dessous.

Ce lot prolonge la [première application des guides](APPLICATION_V72.md), à partir
du commit [`5a69f03603a2250d3a4c0fcd39752fd79eb980c7`](https://github.com/darknigthmare/massilia-cyberpunk/tree/5a69f03603a2250d3a4c0fcd39752fd79eb980c7),
dans la [PR #4](https://github.com/darknigthmare/massilia-cyberpunk/pull/4).
Les [empreintes des sources](../qa/v72-hud/sources.json) identifient les fichiers
de cette passe ; le commit de départ ne désigne pas à lui seul les sources modifiées.

Le guide [game-ui-ux][ui], épinglé à
`19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9`, est appliqué au moteur WebGL2 et
aux menus existants selon le [guide local](GAMEDEV_SKILLS.md) : rendre les
informations lisibles aux formats contrôlés, conserver leurs propriétaires et
vérifier le parcours d'ouverture, de fermeture et de reprise dans le vrai jeu.

## Problème constaté

Les panneaux hérités utilisaient des positions absolues ou fixes indépendantes.
Le GPS, les objectifs et le contexte urbain occupaient des emplacements communs ;
les informations de progression, les statistiques et les panneaux du bas pouvaient
également se recouvrir. L'[inventaire avant correction](../qa/v72-hud/before/inventory.json)
conserve les rectangles et les textes observés.

| Format | Avant | Après |
| --- | --- | --- |
| 1280 × 720 | [Capture initiale](../qa/v72-hud/before/1280x720.png) | [HUD réorganisé](../qa/v72-hud/hud-1280x720.png) |
| 1024 × 768 | [Capture initiale](../qa/v72-hud/before/1024x768.png) | [HUD réorganisé](../qa/v72-hud/hud-1024x768.png) |

Ces captures documentent l'implantation des panneaux. Elles ne garantissent pas
un instant de simulation identique et ne constituent pas une comparaison de leurs
compteurs ou de leurs performances.

Une première vérification des rectangles de panneaux ne suffisait pas à détecter
la valeur d'intégrité `100/104` répartie sur deux lignes. La colonne des valeurs
utilise désormais la largeur de son contenu, avec des chiffres tabulaires et sans
retour à la ligne. Le test final mesure aussi les fragments du texte de vie et
d'armure, et pas seulement la boîte de leur panneau.

## Composition en huit zones

Le module [`hud-layout-runtime.js`](../../game/src/v72/hud-layout-runtime.js)
déplace les nœuds existants dans `.game > .hud > #v72-hud-layout` et les répartit
en huit zones. Les composants gardent leurs identifiants, leur contenu et leurs
gestionnaires ; les systèmes du jeu continuent à actualiser leurs propres valeurs.

| Zone | Contenu organisé |
| --- | --- |
| En-tête — `header` | Titre de l'édition, horloge et nom de la zone |
| Navigation — `navigation` | GPS, itinéraire, objectifs et contexte urbain |
| Alertes — `alerts` | Notifications et panneaux conditionnels de poursuite, de combat ou d'intrusion |
| Statut — `status` | Crédibilité, crédits, accès aux dossiers, progression et indications de sauvegarde |
| Vitalité — `vitals` | Niveau, intégrité, blindage et autres statistiques du personnage |
| Contexte — `context` | Cellule géographique, relief et consommables rapides |
| Combat — `combat` | Cortex, arme, précision, posture et informations de véhicule lorsqu'elles sont actives |
| Pied — `footer` | Attribution des données géographiques |

La grille adapte les colonnes, les espacements et les retours de texte à la largeur
disponible. Le déplacement conserve notamment la relation `.hud .stats` utilisée
par le HUD corporel. Un observateur limité aux insertions directes dans les parents
existants accueille les panneaux créés plus tard ; il ne suit pas leurs mises à
jour de texte à chaque image.

Les règles de visibilité font partie du changement : les nœuds portant `hidden`
restent masqués, les notifications concernées attendent leur état `.on`, et le HUD
ainsi que ses descendants sont masqués lorsqu'une modale ou le menu v34 est ouvert.
Les boutons et liens conservent leurs interactions ; elles sont désactivées avec
le HUD pendant ces menus. La barre de consommables `#quick28` reste masquée à
760 px et moins, conformément à la règle héritée.

L'extension [`v72_hud.py`](../../game/tools/v72_hud.py), déclarée dans
[`build_v72.py`](../../game/build_v72.py), ajoute le module après les propriétaires
existants et l'intègre aux empreintes d'entrée. Elle refuse une injection en double
ou un conteneur parent absent ou ambigu. Les sources parentes gelées et leurs
empreintes de protection restent inchangées. Le lot n'ajoute ni ressource de jeu,
ni donnée géographique, ni domaine de sauvegarde.

## Vérification du HUD dans le navigateur

Le [`hud_browser_smoke.cjs`](../../game/tests/v72/hud_browser_smoke.cjs) a été
exécuté du **29 octobre 2026 à 13:52:41 au 29 octobre 2026 à 13:55:47 UTC**,
avec Chromium **156.0.8078.73** et Playwright **1.56.1**, dans un contexte neuf,
en français et sans interface, avec WebGL logiciel demandé.
Le [rapport complet](../qa/v72-hud/report.json) conserve les observations et les
assertions ; sa sérialisation JSON compacte ne retire aucune donnée du rapport.

| Parcours | Formats et résultat |
| --- | --- |
| Exploration initiale | 1920 × 1080, 1440 × 1000, 1280 × 720, 1024 × 768, puis retour à 1440 × 1000 |
| Cortex ouvert par **Maj+F1** | Les quatre formats précédents, puis 700 × 800 |
| Reprise après le bouton de fermeture | Bouton réellement défilé dans la zone visible et cliqué à 700 × 800 ; HUD contrôlé ensuite à 1440 × 1000 |
| Entrée par le menu existant | **Tab → Cortex urbain → Augmentations actives**, contrôle à 1440 × 1000, puis fermeture par **Maj+F1** |

Sur les six relevés d'exploration, les **19 panneaux requis** sont présents une
seule fois dans les huit zones, visibles et contenus dans le viewport. Aucun
chevauchement entre ces panneaux ni débordement horizontal n'est relevé, avec
une tolérance d'assertion de **1 pixel CSS**. Leurs références de nœuds sont
identiques après redimensionnements et passages dans les menus ; cette comparaison
commence après leur montage initial.

Les valeurs `100/104` pour l'intégrité et `65/120` pour le blindage occupent
chacune **une ligne** dans tous ces relevés. `Range.getClientRects()` contrôle
leurs fragments de texte et l'absence de chevauchement avec leur barre et leur
libellé respectifs.

Le Cortex reste contenu dans la fenêtre, sans débordement horizontal, avec ses
trois commandes de capacité et son bouton de retour. Son défilement vertical
normal est autorisé : un bouton situé plus bas dans le contenu n'est pas assimilé
à un élément masqué. À **700 × 800**, le bouton de retour est amené dans la zone
visible puis actionné sans clic forcé. Après reprise réelle du jeu, sans menu
ouvert, `#quick28` conserve bien `display: none`. La
[capture du Cortex](../qa/v72-hud/cortex-700x800.png) accompagne ce contrôle limité.

Pendant les pauses réelles des menus, les comparaisons conservent les **1 440
crédits**, la zone `geo:V52-MC-33`, le domaine persistant `core.v70` et les **100
unités d'énergie du cyberdeck**. Le test HUD n'active aucune augmentation et n'écrit
pas ces valeurs. Il vérifie aussi qu'aucun descendant du HUD ne reste visible
au-dessus des menus. Le rapport final ne contient **aucune exception de page,
erreur console, erreur HTTP, requête échouée ou avertissement**.

## Continuité rejouée sur la nouvelle campagne

Le [`browser_smoke.cjs`](../../game/tests/v72/browser_smoke.cjs) a été rejoué
indépendamment à **1440 × 1000**, du **29 octobre 2026 à 13:52:40 au 29 octobre
2026 à 13:55:18 UTC**. Ses **11 étapes réussissent** : entrée dans Marseille,
Cortex, activation du Rempart, export/import groupé réel, rechargement, survol,
inspecteurs et retour à la campagne. Le
[rapport de continuité](../qa/v72-hud/continuity/report.json) décrit notamment la
pause utilisée pour comparer les délais et l'ajout temporaire de 17 crédits
destiné à prouver la restauration par l'import.

Le survol conserve exactement les **16 valeurs de stockage local** comparées.
Il utilise le centre installé en mode `fallback-centre`. L'inspecteur
d'architecture sélectionne réellement `osm/way/67716270`, dont la hauteur reste
estimée et la fidélité non certifiée. L'inspecteur de voirie est ouvert mais
retourne **`occluded`** ; aucune sélection routière réussie n'est revendiquée.

Ce parcours conserve trois événements attendus liés à la même absence de données :
**un HTTP 404** du manifeste métropolitain facultatif, **une erreur console**
correspondante et **une annulation du corps de cette réponse**. L'exception exige
le manifeste exact, le 404 journalisé et le rendu effectif du repli ; l'annulation
du fetch doit correspondre à la même étape. Aucune exception de page ni aucun
avertissement n'est relevé, et aucune autre panne réseau n'est admise.

Les captures de ce second parcours sont conservées :
[campagne](../qa/v72-hud/continuity/01-campaign-real-marseille.png),
[Cortex](../qa/v72-hud/continuity/02-cortex.png),
[survol](../qa/v72-hud/continuity/03-flyover-installed-data.png),
[architecture](../qa/v72-hud/continuity/04-inspector-architecture.png) et
[voirie occultée](../qa/v72-hud/continuity/04-inspector-road.png).

## Tests de code et reconstruction

| Contrôle final | Résultat |
| --- | --- |
| Suite JavaScript v72 | **62 tests : 60 réussis, 2 sautés, 0 échec** |
| `test_build_v72.py` | **10 réussis**, aucun saut |
| `test_viewer_build_v72.py` | **9 réussis**, aucun saut |
| `test_launch_cache_v72.py` | **13 réussis**, aucun saut |
| Total des trois suites Python ci-dessus | **32 réussis, 0 échec, 0 erreur, 0 saut** |
| Reconstruction courante | **27 originaux vérifiés** ; campagne et survol reconstruits |

Les [sorties JavaScript](../qa/v72-hud/javascript-tests.txt), les
[sorties Python](../qa/v72-hud/python-tests.txt) et leur
[récapitulatif](../qa/v72-hud/python-summary.json) sont conservés séparément.
Les deux sauts JavaScript concernent les données métropolitaines préparées
absentes de cette copie : le rectangle routier source de 0,5 m et le trajet réel
AMP Belsunce–République. Les étapes navigateur ne sont pas additionnées aux
tests unitaires pour annoncer un total unique.

| Sortie locale reconstruite | Octets | SHA-256 |
| --- | ---: | --- |
| `SOMA_MASSILIA_URBAIN_v0_72.html` | 64 263 418 | `77f09426c0c68ec2702f8ce8cc46b75d5005d468d2988416f6cbe92155ae1c50` |
| `metropole-viewer-v72.html` | 1 775 416 | `b0d2910a557c59197303a2907537d413a0d6c856d63bd2cdf8b6052d322863c7` |

Le HTML de campagne change avec le HUD. Le HTML du survol reste identique à celui
du lot précédent ; son rapport de reconstruction tient compte des nouvelles
entrées de la v72. Les [reçus de campagne](../qa/v72-hud/build-report.json) et
[de survol](../qa/v72-hud/viewer-build-report.json) attestent chacun le contrôle
des 27 originaux. Les HTML générés et les caches restent hors du dépôt.

### Commandes de reproduction

Depuis la racine, après une préparation complète et les prérequis décrits dans
[VALIDATION.md](VALIDATION.md) :

```sh
python3 game/tools/build_metropole_viewer_v72.py
python3 game/build_v72.py
node --test --test-concurrency=2 game/tests/v72/*.test.cjs
python3 -m unittest discover -s game/tests/v72 -p 'test_build_v72.py'
python3 -m unittest discover -s game/tests/v72 -p 'test_viewer_build_v72.py'
python3 -m unittest discover -s game/tests/v72 -p 'test_launch_cache_v72.py'
python3 game/tools/serve_v72.py --no-browser --port 8872
```

Dans un autre terminal, avec Playwright installé, remplacer
`/chemin/vers/chromium` par l'exécutable choisi. Si le Chromium géré par Playwright
est installé, omettre `--chromium` :

```sh
node game/tests/v72/hud_browser_smoke.cjs \
  --url http://127.0.0.1:8872/SOMA_MASSILIA_URBAIN_v0_72.html \
  --chromium /chemin/vers/chromium \
  --output test-results/v72-hud
node game/tests/v72/browser_smoke.cjs \
  --url http://127.0.0.1:8872/SOMA_MASSILIA_URBAIN_v0_72.html \
  --chromium /chemin/vers/chromium \
  --output test-results/v72-hud-continuity
```

Les deux scripts ouvrent un contexte navigateur neuf et n'utilisent pas le profil
ou la sauvegarde habituels du joueur. Playwright reste une dépendance facultative
de validation, sans ajout au runtime du jeu.

## Limites de cette passe

- Le contrôle HUD qualifie la scène initiale et ses 19 panneaux requis. Les
  surimpressions conditionnelles de combat, de police et de véhicule ne sont pas
  activées dans ce scénario.
- **700 × 800** qualifie le menu Cortex et la règle de masquage des consommables
  après fermeture. Ce résultat ne qualifie ni l'exploration sur écran étroit,
  ni la jouabilité mobile, ni les commandes tactiles.
- Les valeurs de vie et d'armure sont contrôlées pour les valeurs observées.
  Les options de taille de texte du dialogue, la navigation complète au focus,
  la manette et l'accessibilité globale ne sont pas certifiées ici.
- Le parcours de continuité exerce le domaine `core.v70` dans la v72 ; il ne
  remplace pas l'import d'une véritable sauvegarde historique v70/v71. Les états
  radio/netrunner sont constatés vides après restauration, sans combat actif
  préalable dans ce scénario.
- Aucun gain de performances, résultat sur GPU matériel, parcours prolongé ou
  campagne complète n'est déduit de ces exécutions avec rendu logiciel demandé.
- Le cache métropolitain complet reste absent. Le repli du centre, les 92
  destinations administratives et l'ouverture des inspecteurs ne certifient
  ni une couverture métropolitaine complète, ni une traversabilité physique,
  ni une restitution architecturale à 1:1.

[ui]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/game-ui-ux/SKILL.md
