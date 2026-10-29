# Guides gamedev pour Massilia Cyberpunk

Ce document adapte une sélection de guides de développement aux conventions de Massilia.
Il décrit une méthode de contribution et les preuves attendues pour chaque changement.
Une règle documentée ne constitue pas une fonctionnalité livrée ni une validation en jeu.

## Références de travail

- Projet audité : **v0.72**, commit `e1b292a01b720e54d194d9e6f2a4d4b39581b9e8`.
- [Base GitHub du projet](https://github.com/darknigthmare/massilia-cyberpunk/tree/e1b292a01b720e54d194d9e6f2a4d4b39581b9e8).
- Catalogue : `gamedev-skills/awesome-gamedev-agent-skills`.
- Révision du catalogue : `19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9`.
- [Routeur de sélection][router] et [adaptation aux moteurs maison][custom].
- Consignes du dépôt : [AGENTS.md](../../AGENTS.md).
- Vérifications et limites : [VALIDATION.md](./VALIDATION.md).

Les références externes sont épinglées pour rendre les décisions reproductibles.
Les synthèses ci-dessous sont propres au projet ; aucun fichier tiers n'est incorporé.
Toute révision ultérieure du catalogue doit être relue avant de modifier ces consignes.

## Contrat du projet

Massilia utilise du **HTML/JavaScript, un rendu WebGL2 maison et un assemblage Python**.
Les API utiles se vérifient dans les sources, les points d'entrée et les appels existants.
Les exemples Godot, Unity ou Three.js du catalogue servent à comprendre les concepts.
Ils doivent être traduits vers les interfaces réellement présentes dans Massilia.
Conserver les versions et la chaîne d'assemblage du projet ; aucune migration n'est induite.
L'adoption de ces références ne nécessite aucune installation globale de compétences.

Les sources historiques **v66 à v71 restent gelées**.
Les évolutions doivent suivre la chaîne de production de la version courante.
Avant une modification, identifier le fichier source qui produit le livrable visé.
Éviter toute correction limitée à un fichier généré que le prochain assemblage écraserait.
Comparer le résultat généré à la base et expliquer les changements effectivement produits.

Le territoire comporte deux périmètres distincts :

- la **campagne du centre de Marseille, organisée en 168 cellules** ;
- le **survol de la métropole, couvrant 92 communes**.

Conserver cette distinction dans les données, la navigation et les comptes rendus.
Les données géographiques proviennent notamment d'**OSM et de l'IGN**.
Documenter la source, l'emprise, les transformations et les limites des données modifiées.
Un élément procédural ou extrapolé doit être identifié comme tel.
Il ne doit jamais être présenté comme une mesure ou un relevé géographique réel.

## Sélection avant chaque chantier

1. Décrire le comportement attendu et le problème observé, avec un exemple reproductible.
2. Lire les consignes locales et repérer une fonction existante proche du besoin.
3. Choisir les guides nécessaires, **généralement un à trois**, selon le changement prévu.
4. Lire leur contenu à la révision épinglée et vérifier leurs hypothèses contre le projet.
5. Associer chaque concept retenu à un fichier, un symbole et un appel existants.
6. Définir une preuve de réussite observable avant de modifier le comportement.
7. Exécuter les vérifications pertinentes de [VALIDATION.md](./VALIDATION.md).
8. Rapporter le résultat obtenu, les limites et les scénarios restant à observer.

Le routeur facilite cette sélection ; il ne déclenche aucune installation automatique.
Pour une API inconnue, rechercher le contrat dans le code ou la documentation disponible.
Nommer explicitement ce qui reste inconnu et limiter les changements à ce qui est vérifiable.

## Guides retenus

Chaque critère ci-dessous est une cible de validation pour un chantier concerné.
Le tableau ne déclare aucune de ces fonctionnalités déjà implémentée ou testée.

| Guide | Quand le lire | Adaptation à Massilia | Critère de réussite |
| --- | --- | --- | --- |
| [level-design][level] | Parcours, accès, rencontres, quartiers | Vérifier les dimensions du contrôleur, les liaisons de cellules et les prérequis ; conserver la géographie documentée. | Le parcours requis atteint son objectif sans passage impossible ni verrou circulaire. |
| [save-systems][save] | Persistance, reprise, évolution du format | Utiliser le stockage réellement employé ; conserver identifiants stables, version et état intermédiaire. | Après fermeture et relance, les données pertinentes sont restaurées ; une sauvegarde invalide est gérée explicitement. |
| [performance-optimization][perf] | Ralentissement ou coût d'un ajout | Mesurer le rendu WebGL2, la logique et les allocations sur un parcours fixe avant de choisir une optimisation. | Comparaison avant/après à conditions égales, avec temps de trame et limites de mesure indiqués. |
| [create-game-assets][assets] | Sprites, textures, décors, interfaces | Conserver palette, échelle, vue, ancrages et conventions ; contrôler les ressources au format réellement utilisé. | Dimensions et transparence adaptées, cohérence visuelle et inspection dans une scène représentative. |
| [rpg][rpg] | Quêtes, équipement, progression, récompenses | Appliquer seulement les systèmes présents ou demandés ; réutiliser les schémas et propriétaires d'état existants. | Progression persistante, récompense unique et équipement réversible sans dérive des valeurs. |
| [dialogue-systems][dialogue] | Choix, conditions, conséquences narratives | Réutiliser le format narratif existant ; séparer affichage, variables et effets des transitions. | Chaque branche atteint une issue valide et ses effets attendus se produisent une seule fois. |
| [game-ui-ux][ui] | HUD, menus, surimpressions | Vérifier état initial, actualisation, reprise après chargement, focus et formats d'affichage pris en charge. | Informations exactes et parcours des menus complet, sans commande bloquée ni contenu coupé. |
| [input-systems][input] | Commandes, clavier, manette, remappage | Relier les actions aux entrées du projet ; distinguer maintien et appui unique, respecter AZERTY/QWERTY. | Une action discrète se déclenche une fois ; les commandes annoncées restent utilisables après reprise. |
| [game-ai][ai] | Perception, poursuite, navigation des PNJ | Séparer perception, décision et déplacement ; préserver la visibilité réelle et la dernière position connue. | Aucune connaissance de la position courante sans information sensorielle ou contact valide ; transitions cohérentes et récupération après blocage. |
| [game-feel][feel] | Impacts, sons, particules, secousses | Brancher les effets sur des événements réels ; respecter pause, ralenti, collisions et options de confort. | Effet proportionné, fin propre, contrôle conservé et absence de modification involontaire de la simulation. |

## Points d'adaptation à contrôler

### Monde et progression

Pour modifier une cellule, vérifier ses raccords, entrées, sorties et objectifs voisins.
Un objectif doit être atteignable avec les moyens disponibles à ce stade de la campagne.
Une navigation réussie sur le survol ne valide pas automatiquement le parcours de campagne.
Les ajouts géographiques conservent une provenance et une qualification de leur précision.

### Perception et combat

Préserver l'invariant d'**absence d'omniscience** dans toutes les décisions des PNJ.
Une cible cachée peut être recherchée à sa dernière position connue selon les règles du jeu.
L'état interne ne doit pas suivre sa position courante sans information de perception valide.
Les effets d'impact doivent se déclencher depuis le résultat effectif de l'action.
Une animation ou une secousse visuelle ne doit pas déplacer implicitement les collisions.

### État, sauvegarde et interface

Identifier le propriétaire de chaque état avant d'ajouter un second stockage ou un cache.
Vérifier l'état initial du HUD et sa resynchronisation après une reprise ou un chargement.
Conserver les progrès partiels nécessaires à une quête, avec des identifiants stables.
Rejouer une transition ou recharger une scène ne doit pas doubler une récompense.
Adapter la gestion d'échec au stockage réel et préserver les données précédemment valides.

### Mesures et ressources

Décrire machine, navigateur, résolution, parcours et mode d'exécution pour toute mesure.
Une cible de performance reste une cible tant qu'une mesure représentative ne la confirme pas.
Un contrôle statique de ressources ne valide ni leur lisibilité ni leur rendu WebGL2.
Une ressource visuelle nécessite une inspection à sa taille d'usage et dans son contexte.

## Statuts et preuves

| Statut | Sens dans le suivi | Preuve minimale |
| --- | --- | --- |
| **Documenté** | Le comportement attendu et ses critères sont décrits. | Fichier de référence et périmètre. |
| **Implémenté** | Le changement existe dans les sources de la version concernée. | Commit et fichiers modifiés. |
| **Testé** | Une vérification précise a été exécutée. | Commande ou scénario, résultat, version et limites. |
| **Observé** | Le comportement a été constaté dans le jeu lancé. | Parcours, environnement et observation ; capture si utile. |

Renseigner les statuts séparément et les rattacher à une révision.
Un assemblage réussi ne prouve pas que le jeu démarre ni que le parcours est jouable.
Le validateur du catalogue contrôle ses guides et ressources ; il ne remplace pas la QA du jeu.
Conserver les échecs et vérifications non exécutées dans le compte rendu de contribution.
Cette intégration documentaire fournit un cadre ; ses effets sur le gameplay restent à démontrer.

## Liens sources épinglés

[router]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/router/SKILL.md
[custom]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/router/references/custom-engines.md
[level]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/level-design/SKILL.md
[save]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/save-systems/SKILL.md
[perf]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/performance-optimization/SKILL.md
[assets]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/create-game-assets/SKILL.md
[rpg]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/genres/rpg/SKILL.md
[dialogue]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/dialogue-systems/SKILL.md
[ui]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/game-ui-ux/SKILL.md
[input]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/input-systems/SKILL.md
[ai]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/game-ai/SKILL.md
[feel]: https://github.com/gamedev-skills/awesome-gamedev-agent-skills/blob/19d93f97c9c1ea0f8b306e77aa81e0d3e352d3e9/skills/disciplines/game-feel/SKILL.md
