# Massilia Cyberpunk — consignes de développement

Ces consignes s'appliquent à tout le dépôt. Respecter les demandes et autorisations de l'utilisateur ; les guides externes restent des références techniques adaptées au projet.

## Commencer sur la bonne version

La base vérifiée lors de l'introduction de ces consignes est **v0.72**, commit `e1b292a01b720e54d194d9e6f2a4d4b39581b9e8` du dépôt `darknigthmare/massilia-cyberpunk`, le 29 octobre 2026. Avant un nouveau chantier, vérifier la branche, son état et les changements plus récents ; cette référence est un point de comparaison, pas une instruction de revenir en arrière.

Lire le [README](README.md), le guide de l'édition courante et les sources/tests du système concerné. Les rapports des versions antérieures décrivent leur propre validation ; ils ne prouvent pas celle d'un nouveau changement.

## Architecture à conserver

- Le jeu est une application HTML/JavaScript, avec rendu WebGL 2 natif et outils Python. Le survol utilise notamment `createRenderer(canvas)` dans `game/src/v69/metropole-viewer.js`. Python sert à préparer/lancer le jeu ; Node.js sert aux tests.
- Le point d'entrée utilisateur est `lancer.py` à la racine, ou `LANCER_JEU.cmd`. Les HTML sont reconstruits depuis les données et extensions versionnées.
- Vérifier la chaîne de build avant de modifier un module : `game/build_v72.py` contrôle `FROZEN_PARENT_SOURCES`, `PARENT_SHA256`, `inputs()` et `require_unchanged()`. Les parents v0.66–v0.71 et les 27 originaux protégés sont des références immuables pour cette édition.
- Faire évoluer l'extension courante ou créer une édition suivante selon le contrat existant. Une refonte des parents gelés exige un chantier explicite et une nouvelle preuve de reconstruction. Ne pas actualiser leurs empreintes simplement pour masquer une modification.
- Modifier les sources de génération, puis reconstruire les sorties. Les HTML générés, reçus locaux et caches géographiques ignorés par Git ne sont pas des sources à éditer ou ajouter au dépôt.
- Garder les conventions de cycle de vie, de temps, d'entrée, de stockage et de nettoyage déjà utilisées. Lire un exemple fonctionnel et son appel réel avant de proposer une nouvelle API.

## Utiliser les guides gamedev

Le [guide de sélection](docs/development/GAMEDEV_SKILLS.md) relie les chantiers de Massilia à `awesome-gamedev-agent-skills`, référence `19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9`.

1. Identifier le problème et ses fichiers propriétaires.
2. Choisir les guides strictement nécessaires, généralement un à trois ; lire leurs fichiers et références utiles à la révision indiquée.
3. Appliquer les concepts aux API vérifiées du moteur maison. Les exemples Godot, Unity, Unreal ou Three.js ne sont pas des dépendances à introduire.
4. Définir un comportement observable et un contrôle adapté avant de modifier le système.
5. Vérifier le résultat avec la [procédure de validation](docs/development/VALIDATION.md), puis consigner ce qui a réellement été exécuté et observé.

Si une référence externe devient inaccessible, conserver les contraintes vérifiées du projet, signaler la référence manquante et continuer ce qui peut être établi par le code local. Ne pas inventer le contenu d'un guide. Une mise à jour du catalogue doit être relue et explicitement référencée.

## Invariants de Massilia

### Géographie et jouabilité

- La campagne physique v0.72 couvre 168 cellules du centre, soit 10,5 km². Le survol métropolitain est indépendant et couvre les données installées des 92 communes. Une copie Git seule se replie explicitement sur le centre disponible.
- Distinguer données acquises, surface affichée, graphe NAV préparé, itinéraire calculé et passage physiquement jouable. Un résultat de routage ne prouve pas à lui seul la traversabilité.
- Préserver les identités OSM, coordonnées Lambert-93/EPSG:2154, unités métriques, altitudes NGF-IGN69 et masques NoData. Les hauteurs à l'égout, au faîtage et les altitudes de sol ont des significations différentes.
- Les façades, toits, largeurs ou ouvrages estimés restent identifiés comme tels. Ne pas combler une inconnue de source par un volume, une collision ou un raccord puis l'annoncer comme relevé réel.
- Pour un changement de géométrie, conserver une preuve de source et vérifier relief, limites de cellule, trous/cours, occlusions et collisions. Le level design s'adapte à la géographie documentée et aux capacités mesurées du personnage.
- Le cache métropolitain complet est une dépendance externe au dépôt : sa disponibilité se vérifie dans l'environnement courant, sans reprendre une affirmation d'un ancien rapport.

### Sauvegarde, ressources et commandes

- Identifier le propriétaire existant avant d'ajouter de l'état. Les augmentations passent par le cyberdeck v42 et le domaine `core.v70` ; la v0.72 conserve la continuité v0.70/v0.71.
- Contacts radio, préparation d'attaque et inspection v0.72 sont éphémères. Leur ajout ne justifie pas un domaine `core.v72`, une seconde réserve d'énergie ou un sérialiseur parallèle.
- Charger/importer une sauvegarde doit réinitialiser les états temporaires tout en respectant les délais et compteurs persistants. Vérifier les transitions avec le sérialiseur réel.
- Préserver les raccourcis des consommables `F1–F4` et ceux du Cortex `Maj+F1–F4`. Tester les interactions avec les menus, la pause et la reprise.

### IA et combat

- Les décisions utilisent les contacts réellement observés/entendus et leur dernière position connue. Une réception radio conserve provenance et expiration ; elle ne devient pas une observation personnelle fraîche.
- La seule radio ne permet pas de tirer ou d'arrêter le joueur. Garder les règles de perception, factions, portée, invalidation d'identité et budgets du système.
- La préparation netrunner respecte le propriétaire de l'effet et son délai de récupération, y compris lors d'une interruption. Vérifier perte de vue, coup reçu, pause, décès, conduite, import et changement de zone.
- Les effets visuels/sonores expriment un événement réel. Ils ne changent pas implicitement la visée, les dégâts, les collisions ou l'état de pause.

### Rendu et performances

- Mesurer avant d'optimiser : même build, trajet, matériel, résolution et état de cache. Rapporter temps de trame, pointes et mémoire mesurée ; préciser les limites des mesures CPU/GPU disponibles.
- Les budgets de streaming, de lecture, de calcul et de ressources GPU existants font partie du contrat. Vérifier annulation, changement de scène et libération des anciens buffers.
- Conserver une direction artistique méditerranéenne cyberpunk cohérente, avec les accents cyan, magenta et ambre du projet. Évaluer les assets dans le jeu à leur échelle réelle.

## Vérifier et livrer

Les commandes exactes et leurs prérequis sont dans [VALIDATION.md](docs/development/VALIDATION.md). Utiliser les contrôles pertinents pour le périmètre modifié ; élargir seulement pour un risque identifié ou une exigence du projet.

Pour une modification purement documentaire, vérifier chemins, liens, commandes et diff sans inventer de tests de gameplay. Pour du code, distinguer tests unitaires, reconstruction réelle, tests navigateur et observations humaines. Le smoke historique v0.68/v0.69 ne qualifie pas la v0.72.

Dans la PR, indiquer le problème joueur, les systèmes touchés, les preuves avant/après utiles, les commandes exécutées avec résultats et tests sautés, puis les limites restantes. Réserver « vérifié dans le jeu » aux comportements réellement observés. Ne pas confondre un contrôle automatique réussi avec une campagne complète ou une fidélité architecturale 1:1.

Après les vérifications nécessaires, livrer le changement autorisé sans ajouter de campagnes de tests sans objectif.
