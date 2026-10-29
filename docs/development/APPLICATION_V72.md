# Première application des guides gamedev à Massilia v0.72

## Résultat et périmètre

Le 29 octobre 2026, le cadre décrit dans [GAMEDEV_SKILLS.md](GAMEDEV_SKILLS.md)
a été appliqué à un défaut de couverture du routage et à un parcours navigateur
de la version courante. Base du jeu :
[`e1b292a01b720e54d194d9e6f2a4d4b39581b9e8`](https://github.com/darknigthmare/massilia-cyberpunk/tree/e1b292a01b720e54d194d9e6f2a4d4b39581b9e8).
La documentation initiale figurait dans le commit
`3c8f9727d65b4fc6e88b919f10a07585a39ee380` de la branche
`codex/gamedev-guidance-v72`.

Le changement est suivi dans la [PR #4](https://github.com/darknigthmare/massilia-cyberpunk/pull/4).
Les résultats ci-dessous concernent les sources de cette application, identifiées
par leurs empreintes dans [sources.json](../qa/v72-gamedev/sources.json).
Ils ne remplacent pas le rapport historique de livraison v72.

## Défaut reproduit et correction

Le catalogue du routeur ignorait entièrement une cellule connue du manifeste
lorsqu’elle ne possédait pas de descripteur de navigation. Une lacune de préparation
pouvait ainsi être annoncée comme un corridor entièrement vérifié.

La régression reproduit trois cellules consécutives : les extrémités ont des graphes
valides et la cellule centrale n’a pas de descripteur NAV.

| Observation sur cette régression | Avant | Après |
| --- | --- | --- |
| Statut du calcul | `no_route_in_loaded_network` | `corridor_incomplete` |
| Couverture annoncée complète | `true` | `false` |
| Cellules demandées | 2 | 3 |
| Cellule centrale signalée manquante | Non | Oui |
| Graphes effectivement chargés | 2 | 2 |

La correction conserve les métadonnées bornées des cellules non préparées dans
[`route-corridor-core.js`](../../game/src/v72/route-corridor-core.js).
Ces cellules participent à la sélection du corridor, à son budget de cellules
et au budget des métadonnées résidentes. Elles alimentent `missingCells`, sans
déclencher de lecture de fichier inexistant. La fusion des graphes conserve les
identités et jonctions natives ; aucune liaison géographique n’est ajoutée.

Les trois nouveaux cas de
[`route-corridor.test.cjs`](../../game/tests/v72/route-corridor.test.cjs)
distinguent une cellule sans descripteur, un asset NAV répondant 404, un graphe vide
mais vérifié, puis les refus liés aux budgets. Ils contrôlent aussi l’absence de
mutation du manifeste et la libération des graphes. La nouvelle régression échouait
sur le code précédent et réussit avec la correction.

## Application au contrôle des sauvegardes et de l’interface

Le nouveau [`browser_smoke.cjs`](../../game/tests/v72/browser_smoke.cjs) applique
les critères de sauvegarde et d’interface du guide local aux propriétaires réels
de Massilia. Le moteur WebGL2, le cyberdeck v42, le domaine persistant `core.v70`
et le sérialiseur groupé existant sont utilisés directement.

Le test ouvre un contexte navigateur neuf, actionne les boutons et les raccourcis
du jeu, active le Rempart, puis exporte et importe réellement une sauvegarde groupée.
Une modification temporaire de 17 crédits prouve que l’import restaure la valeur
exportée. La simulation est mise en pause pour comparer les délais persistants
sans écoulement de temps de jeu. La protection active disparaît lors de l’import,
alors que son délai et son compteur d’activation sont conservés.

La suite poursuit le parcours après rechargement, ouvre le survol indépendant,
exerce les inspecteurs, compare exactement les 16 entrées de stockage local et
revient à la campagne par le lien prévu. Elle n’utilise aucun profil joueur.
Playwright reste un outil facultatif de QA ; il n’entre pas dans le runtime du jeu.

## Vérifications exécutées

Les commandes partent de la racine du dépôt. L’environnement de test utilisait
Python 3.12 et Node.js 22.20.0. Le navigateur était Chromium 156.0.8078.73,
piloté avec Playwright 1.56.1, en mode sans interface, avec WebGL logiciel demandé
et une fenêtre de 1440 × 1000 pixels. Les identifiants précis du navigateur et
le déroulement figurent dans le rapport brut.

| Vérification | Résultat |
| --- | --- |
| `python3 lancer.py --prepare-only` avant correction | Préparation complète réussie ; 27 originaux vérifiés et centre de 168 cellules préparé |
| `node --test --test-concurrency=2 game/tests/v72/*.test.cjs` après correction | 62 tests : **60 réussis, 2 sautés, 0 échec** |
| `python3 -m unittest discover -s game/tests/v72 -p 'test_build_v72.py'` | **10 réussis**, avec le parent v71 reconstruit présent |
| `python3 -m unittest discover -s game/tests/v72 -p 'test_route_patch.py'` | **3 réussis** |
| `python3 -m unittest discover -s game/tests/v72 -p 'test_viewer_build_v72.py'` | **9 réussis** |
| `python3 game/tools/build_metropole_viewer_v72.py` puis `python3 game/build_v72.py` | Reconstruction finale réussie ; 27 originaux vérifiés |
| `node game/tests/v72/browser_smoke.cjs --url http://127.0.0.1:8872/SOMA_MASSILIA_URBAIN_v0_72.html --chromium <chromium-local> --output /tmp/massilia-v72-smoke-final` | **11 étapes réussies**, du 29/10/2026 13:07:59 au 29/10/2026 13:10:05 UTC |

Le serveur était lancé par `python3 game/tools/serve_v72.py --no-browser --port 8872`.
La [procédure de validation](VALIDATION.md) donne une installation reproductible
des prérequis facultatifs. Le chemin `<chromium-local>` désigne ici l’exécutable
Chromium indépendant utilisé pour cette exécution, pas une commande à copier telle quelle.

Les deux tests JavaScript sautés sont :

- `real delivered .5m source rectangle changes rendered native-DEM road triangles and preserves all source files` ;
- `historical conformance72: real AMP world: Belsunce to République uses verified sectors and actual native turns`.

Ils nécessitent les données métropolitaines préparées, absentes de cette copie.
Les résultats des sous-suites ciblées ne sont pas additionnés une seconde fois
aux 62 tests de la suite v72. La suite historique globale v67–v71 n’a pas été
annoncée comme réexécutée dans cette application.

### Empreintes des sorties reconstruites

| Sortie locale générée | Octets | SHA-256 |
| --- | ---: | --- |
| `SOMA_MASSILIA_URBAIN_v0_72.html` | 64 255 096 | `5d0b1a1dccdc304c10121b9b902f8cc84ba5818440af297ff19c8f6928df2429` |
| `metropole-viewer-v72.html` | 1 775 416 | `b0d2910a557c59197303a2907537d413a0d6c856d63bd2cdf8b6052d322863c7` |

La correction appartient au routeur du survol : l’empreinte du HTML de campagne
reste donc identique. Les HTML générés et les caches demeurent hors du dépôt.
Les sources parentes gelées et les empreintes de protection ne sont pas modifiées.

## Ce qui a été observé dans le navigateur

- La campagne v72 entre dans la cellule `geo:V52-MC-33` : 230 bâtiments et
  81 éléments de voirie sont présents ; WebGL2 est actif, son programme est lié
  et son contexte n’est pas perdu.
- **Maj+F1** ouvre le Cortex et son bouton de retour reprend le jeu. Le Rempart
  est activé par son vrai bouton avant les contrôles de sauvegarde.
- L’import, le rechargement et le retour du survol restaurent les 1 440 crédits,
  la zone enregistrée et le domaine persistant `core.v70`. Aucun domaine `core.v71`
  ou `core.v72` n’est ajouté.
- Le survol utilise réellement `data/v69/world/manifest.json` en mode
  `fallback-centre`, avec un index de 168 cellules. La capture montre une scène
  encore en cours de streaming, pas le chargement intégral de toutes les cellules.
- L’inspecteur d’architecture sélectionne `osm/way/67716270`. Sa hauteur reste
  explicitement estimée et sa fidélité architecturale non certifiée.
- L’inspecteur de voirie indique **`occluded`** : le réticule rencontre une surface
  occultante. L’ouverture, le message et la fermeture sont observés ; aucune
  sélection routière réussie n’est revendiquée.
- Le survol et les inspecteurs conservent exactement les 16 valeurs de stockage
  local de la campagne. Le retour restaure sa continuité.
- Aucune exception de page ni erreur WebGL n’est relevée sur ce parcours.

Le manifeste métropolitain facultatif répond 404, puis le lecteur existant annule
le corps de cette réponse. Le rapport conserve le 404, l’erreur de ressource console
et `net::ERR_ABORTED`. Leur classement comme repli attendu exige le même URL,
le même événement de chargement, un HTTP 404 observé et le rendu effectif du centre.
Les autres erreurs restent bloquantes. La première exécution avait échoué uniquement
sur cette annulation ; la condition étroite a été relue, puis le parcours complet
a été rejoué avec succès.

## Preuves et limites

- [Rapport navigateur brut](../qa/v72-gamedev/report.json).
- [Sortie complète des tests JavaScript v72](../qa/v72-gamedev/javascript-tests.txt).
- [Empreintes des sources testées](../qa/v72-gamedev/sources.json).
- [Campagne](../qa/v72-gamedev/01-campaign-real-marseille.png),
  [Cortex](../qa/v72-gamedev/02-cortex.png),
  [survol](../qa/v72-gamedev/03-flyover-installed-data.png),
  [inspection d’architecture](../qa/v72-gamedev/04-inspector-architecture.png),
  [voirie occultée](../qa/v72-gamedev/04-inspector-road.png).

Les captures ont été relues visuellement. Le Cortex et les inspecteurs sont visibles
à la résolution testée. La campagne conserve des superpositions de panneaux du HUD ;
une revue de lisibilité reste nécessaire. La sauvegarde de QA générée localement
est référencée par son empreinte dans le rapport, mais n’est pas versionnée.

Cette passe ne constitue ni une campagne jouée jusqu’au bout, ni une observation
du combat radio/netrunner, ni l’import d’une véritable partie historique v70/v71.
Les états radio/netrunner sont vérifiés vides après restauration sans avoir été
peuplés en combat dans ce scénario. Aucun gain de performances ou résultat sur
GPU matériel n’est déduit du navigateur logiciel. Le routage corrigé est couvert
par ses régressions ; ce smoke ne sélectionne ni ne traverse un nouvel itinéraire.

Les validations restantes sont les imports de sauvegardes historiques, les situations
de combat, les itinéraires sur un cache AMP identifié, la sélection de voirie visible
et les parcours sur plusieurs configurations graphiques. Elles sont distinctes
du correctif reproduit et vérifié livré ici.
