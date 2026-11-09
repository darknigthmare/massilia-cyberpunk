# v0.77 — Recharge, guidage et lecture des sources

Cette édition prolonge la v0.76, intégrée à `main`, et conserve l’ambiance cyberpunk méditerranéenne du projet. Les producteurs des éditions précédentes restent gelés. Les références *Syndicate*, *Cyberpunk 2077* et *E.Y.E: Divine Cybermancy* orientent les systèmes propres à Massilia.

## Lancer

Python 3.11+ et un navigateur WebGL 2 suffisent pour jouer depuis une copie complète du dépôt.

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Sous Windows, utiliser `LANCER_JEU.cmd`. Le premier lancement reconstruit les éditions livrées sans acquisition géographique. Après préparation, `python3 game/tools/serve_v77.py --no-browser --port 8787` sert la campagne et le survol courants. Les lancements suivants réutilisent uniquement les sorties dont les contenus et les entrées sont vérifiés.

## Périmètre

La campagne physique conserve **168 cellules et 10,5 km² du centre**. Le survol indépendant exploite le cache des **92 communes de la métropole**, lorsqu’il est installé ; une copie Git seule affiche explicitement le centre partiel. Le cache lourd reste hors Git. Les imports de continuité gardent leurs propriétaires existants ; aucun domaine de sauvegarde v77 n’est ajouté.

Les cotes, contours, reliefs et masques NoData ne doivent pas être modifiés pour masquer une incertitude de source. L’architecture complète à 1:1 et la traversée physique de toute la métropole restent à réaliser.

## Recharge et commandes

La recharge native27 transférait encore des munitions à l’ancienne arme après un changement par le bouton de l’arsenal27 ou le dépôt29 de l’arme active. La v77 annule cette action dès ces changements et vérifie l’identité de l’arme, du stock, de la scène et de la partie avant le transfert natif. La pause normale conserve le temps restant ; import, décès, récupération ou conduite invalident l’action. Les dégâts, capacités, stocks et propriétaires de sauvegarde ne changent pas. Cette annulation aux transitions incompatibles est un choix de comportement explicite.

## Missions et GPS

Accepter ou terminer une opération, résoudre un appel, avancer une escorte ou franchir un point de course pouvait remplacer ou effacer une destination personnelle. Les transitions automatiques ne modifient désormais qu’une route reconnue par sa destination, son libellé et son mode exacts. Aucun champ de propriété n’est ajouté à la sauvegarde : une destination manuelle parfaitement identique à ce triplet reste indiscernable d’une route de mission.

Les boutons explicites « Tracer » remplacent toujours la destination à la demande du joueur. Les histoires et contrats43 les proposent aussi, avec leurs lieux existants. Une histoire se remet à la table de campagne de **Station Zéro, intérieur A** ; les opérations45 utilisent le centre des opérations **à l’extérieur**. Le GPS conserve les titres des zones source : `station-interiorA` apparaît comme « Clinique des Corps » sur sa prochaine étape. Les contrats retournent au tableau de leur district. « Suivre » conserve son rôle dans le HUD.

Le mode historique du GPS d’acheminement des escortes est conservé : il ne garantit pas un chemin automobile. L’ancien run Port qui vise `corniche-route` reste refusé faute de liaison véhicule connue. Cette édition ne crée aucun raccord pour contourner ces limites.

## Champs IGN et trottoirs

Dans l’Atlas, la fiche des 77 conflits distingue la **référence calculée conservée, sol minimal + hauteur**, des altitudes minimale et maximale de toit issues d’IGN. Les 385 valeurs source ont été contrôlées. Pour 39 objets, l’altitude minimale de toit diffère de cette somme de 0,1 m ; cet écart n’établit pas sa cause et ne justifie aucune translation. Les 77 altitudes minimales de toit sont disponibles ; 41 cotes maximales le sont, les 36 autres restent inconnues.

Le dictionnaire officiel BD TOPO 3.5 décrit notamment des statistiques issues du MNS : les déciles ne donnent ni un contour relevé de toiture ni un point de faîtage localisé. La fiche donne les définitions, la méthode déclarée et l’empreinte du document. Une hauteur nulle signifie inconnue ou non significative ; une altitude NGF nulle reste valide.

L’inspecteur de voirie **J** utilise le côté gauche ou droit de l’axe source pour les trottoirs asymétriques. Un cas réel du boulevard Charles Nédelec était attribué au mauvais côté par l’ancienne largeur maximale. Les unions de surfaces restent ambiguës : un axe compatible n’est pas une preuve de propriété du trottoir. Géométrie, relief, NAV, occlusion et budgets restent conservés.

## Développement et validation

Lire [AGENTS.md](../AGENTS.md), les propriétaires du système concerné et [VALIDATION.md](../docs/development/VALIDATION.md). Le diagnostic `python3 .ai-tools/setup.py doctor` est disponible à la racine ; il distingue les exécutables et fichiers présents des plugins réellement chargés. Cette session n’a pas de compétence Spec Kit ou Superpowers chargée et n’utilise pas Claude Code.

Les résultats de cette édition sont consignés dans [FEATURE_REPORT.json](data/v77/FEATURE_REPORT.json) : **1 041 tests réussis** (671 JavaScript et 370 Python), sans échec ni saut dans les résultats finaux ; **27 étapes navigateur** sur deux profils neufs (20 campagne, 7 survol ; 25 noms distincts). Les anciennes assertions sont réellement rejouées ; les rapports antérieurs ne servent pas de preuve courante.

La préparation et la vérification complètes exécutent 19 builders. Les 144 sources parentes et 32 livrables hérités restent identiques. La vérification a conservé 901 fichiers, leurs dates et 148 fichiers de bytecode. Un miroir de 204 fichiers, sans Git ni cache world/AMP copié, vérifie 5 payloads et 27 originaux et régénère les 168 cellules par le bootstrap stdlib, avec les imports GIS bloqués. Les deux HTML et deux rapports 77 sont identiques au canonique ; 184 entrées transitives correspondent. Le lancement HTTP depuis le reçu valide répond 200 pour les deux HTML sans relancer de builder.

```sh
node --test game/tests/v77/*.test.cjs
python3 -B -m unittest discover -s game/tests/v77 -p 'test_*.py'
```

Pour rejouer les tests Python historiques71–76, utiliser leurs lanceurs exacts en mémoire ; les références Git et la méthode figurent dans le rapport. Les 56 cas Python77 ciblent le lanceur actuel. La QA facultative `browser_current.cjs` accepte `--scope gameplay`, `viewer` ou `all`, avec les options `--url`, `--chromium` et `--output`.

Les captures utilisent Playwright 1.62.1 / Chromium 154 / SwiftShader à 1280 × 720. Les fixtures de pose, stocks, état de quête et santé sont déclarées ; elles ne constituent pas une campagne continue. Le repli navigateur sans cache AMP n’est pas rejoué en77, tandis que sa reconstruction stdlib est vérifiée. Les diagnostics intermédiaires sont conservés hors Git sous `/workspace/massilia-geodata-generated/validation-v77-2026-11-09` et exclus du comptage final. Une restauration dans une nouvelle machine cloud reste à vérifier.
