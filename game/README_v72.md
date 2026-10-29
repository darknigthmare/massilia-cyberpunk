# v0.72 — Contacts radio, contre-jeu neural et corridors routiers

Cette édition poursuit quatre lots : coopération fondée sur des observations réelles, surcharge netrunner interrompable, corridors d’itinéraire plus étendus et fidélité de la voirie. *Syndicate*, *Cyberpunk 2077* et *E.Y.E: Divine Cybermancy* orientent les choix tactiques et l’intrusion, avec des mécaniques propres à Massilia.

## Lancement et continuité

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Le jeu courant est `SOMA_MASSILIA_URBAIN_v0_72.html`, le survol `metropole-viewer-v72.html`. Après préparation, `python3 game/tools/serve_v72.py --no-browser` sert directement cette édition. Les lancements normaux réutilisent des sorties contrôlées par leur contenu ; les cinq payloads, 27 originaux, neuf HTML, rapports et assets des 168 cellules du centre restent vérifiés. Un changement ou une corruption déclenche une préparation complète. Le reçu `data/v72/LAUNCH_CACHE.json` reste local et ignoré par Git.

Les continuités v0.70/v0.71 restent acceptées. Aucun domaine `core.v72` n’est ajouté : radio, préparation ennemie et inspection sont éphémères. Les augmentations héritées utilisent toujours le cyberdeck v42 et `core.v70` ; **Maj+F1** ouvre le Cortex, **Maj+F2/F3/F4** activent ses capacités. Les consommables **F1–F4** gardent leur usage. Les imports effacent les états temporaires tout en conservant les délais et compteurs enregistrés.

## HUD organisé par zones

Le HUD v72 regroupe les panneaux dans huit zones : en-tête, navigation, alertes, statut, état du personnage, contexte géographique, combat et attribution des données. Les panneaux d'origine sont déplacés dans cette disposition en conservant leurs nœuds, identifiants, commandes et propriétaires. Le Cortex tactique rejoint les informations de combat à droite ; les menus masquent le HUD et ses descendants. Les règles d'apparition des panneaux conditionnels restent pilotées par leurs systèmes existants.

Un [smoke navigateur du HUD](tests/v72/hud_browser_smoke.cjs) ajoute les contrôles de visibilité, de chevauchement et de redimensionnement sur 19 panneaux et quatre résolutions, ainsi que les parcours réels du Cortex. Le cas 700 × 800 concerne uniquement le menu ; il n'annonce pas une validation du jeu mobile. Les comparaisons de continuité ont lieu en pause, sans activation de capacité. La commande figure dans la [procédure de validation](../docs/development/VALIDATION.md) ; le [dossier du HUD v72](../docs/development/HUD_V72.md) décrit la disposition et les preuves associées.

## Radio de contacts observés

Les unités compatibles partagent une position échantillonnée au moment d’un contact visuel réel. Caméras, tactiques et police gardent leurs propriétaires de perception ; factions explicites et équipes locales limitent les destinataires. La portée radio est de 48 m dans le plan local de la zone. Aucune précision entre étages n’est prétendue à partir de hauteurs relatives incompatibles.

Une réception fournit une recherche à la dernière position connue. Elle n’autorise ni tir, ni arrestation sans acquisition personnelle. La provenance et l’expiration du contact restent celles du témoin ; les réceptions ne sont pas retransmises comme des observations nouvelles. Une alerte administrative ou un niveau de recherche seul ne fournit pas une position. Les objets remplacés, morts, retirés ou transférés ne conservent pas leurs anciennes identités radio.

La mémoire reste limitée à cinq secondes sans observation renouvelée. Le bus conserve au plus 128 contacts et 512 participants ; ses comparaisons sont bornées. Il ne crée aucun réseau externe, ressource, dégât ou champ de sauvegarde.

## Surcharge netrunner préparée

L’attaque neurale du netrunner prépare désormais son effet pendant **1,1 seconde**. Son télégraphe est visible uniquement si l’unité se trouve réellement dans le champ de caméra, avec une ligne de vue valide et une hauteur corporelle cohérente avec le terrain NGF.

Un coup reçu ou une perte de contact interrompt la préparation. L’interruption conserve le délai de récupération de l’attaque : passer brièvement derrière un obstacle ne lui rembourse pas une attaque immédiatement prête. Les effets d’aveuglement ou brouillage déjà présents sont respectés, sans élargir le ciblage des quickhacks aux humains. L’effet original reste une hausse de tension de 9 et un brouillage d’arme de 2,8 s ; aucun dégât physique ou coût d’augmentation nouveau n’est inventé.

Pause, décès, conduite, récupération, changement de zone et import annulent les préparations. Les boss et ICE numériques conservent leurs systèmes propres. Le nombre de préparations simultanées reste borné à 64 ; le HUD ne montre que les unités visibles.

## Corridors routiers et élargissement explicite

Le panneau **« Itinéraire local »** conserve les deux extrémités du corridor au lieu de charger un simple préfixe de cellules qui pouvait exclure l’arrivée. Le premier calcul couvre au plus **96 cellules**, avec un corridor de 75 m ; **« Élargir le corridor et réessayer »** lance une nouvelle analyse à **192 cellules**, avec un corridor de 250 m. Un précontrôle peut refuser la lecture lorsque la colonne de cellules nécessaire ou le budget de fichiers est déjà connu comme insuffisant.

Les limites initiales sont 24 000 nœuds, 32 000 arêtes, 128 Mio résidents comptabilisés et six secondes. L’élargissement permet 48 000 nœuds et 64 000 arêtes, en conservant le plafond mémoire et le délai. Ces budgets sont des limites de calcul ; ils ne garantissent pas un trajet dans toute la métropole. Les graphes sont libérés après analyse. Le plafond global de deux lectures d’assets et la lecture NAV séquentielle sous verrou de scène restent appliqués.

Une couverture incomplète, une limite et une absence de trajet dans le corridor chargé ont des statuts distincts. Les identités natives, accès, sens uniques, tours et escaliers restent soumis au noyau63 vérifié. Aucun raccord n’est ajouté entre des axes qui se croisent sans jonction source. Les approches libres, ponts, tunnels et conditions non résolues restent exclus ; un détour hors corridor peut exister.

Les cellules déclarées dans le monde mais sans descripteur NAV restent désormais comptées dans le corridor et ses budgets. Elles figurent parmi les cellules manquantes, sans lecture d’asset inventé. Sur le cas de régression à trois cellules, un secteur intermédiaire non préparé produit `corridor_incomplete` et une couverture incomplète. Un graphe vide dont l’intégrité est vérifiée reste, lui, une couverture connue : cette distinction évite d’annoncer à tort un corridor entièrement chargé.

Trois paires réelles ont servi de preuve : un trajet Belsunce–Gillibert de **4 716,83 m sur 41 cellules**, et deux calculs initialement interrompus ou sans trajet local qui trouvent **4 098,89 m** et **4 805,21 m** après élargissement. L’aperçu 2D, les voies nommées et les repères 3D conservent leurs règles v0.71 : rubans découpés contre le MNT natif complet déjà affiché, sans comblement des secteurs absents. La navigation physique métropolitaine reste inactive.

## Fidélité et inspection de voirie

**J** ou **« Inspecter la voirie »** sélectionne une surface routière réellement rendue, en respectant les autres triangles qui la cachent. La fiche présente sa catégorie, les axes source compatibles, les largeurs déclarées et utilisées, les tags d’accès et d’ouvrage, puis l’existence d’une préparation NAV dans ce secteur. Aucun graphe n’est chargé pour cette inspection et ce statut ne certifie aucun passage physique.

Les surfaces préparées peuvent être une union de plusieurs voies. Même un axe compatible unique reste présenté comme un candidat ; les intersections ne reçoivent aucune attribution OSM certaine fabriquée. Les données absentes ou candidats au-delà du budget sont signalés.

L’audit du pack canonique a trouvé une nouvelle cohorte géométrique admissible : `osm/way/1413045827`, cellule `V52-MC-E12-N70`, porte `width='.5'`. Le rendu utilisait 1,8 m par repli. La copie de surface validée utilise maintenant **0,5 m**, avec une aire préparée de **6,785707 → 1,884919 m²**, puis le drapage MNT natif habituel. Identités, empreintes et géométrie isolée sont vérifiées avant correction. Les autres sommets/couleurs et quatre cellules témoins restent identiques. Le cache source et ses graphes NAV ne sont pas réécrits.

Ce respect du tag OSM ne constitue pas une mesure de terrain. Les dimensions de bâtiments et autres paramètres sans source suffisante restent estimés. Le monde conserve 92 communes, 52 020 cellules, les 299 391 références IGN à l’égout et les 71 secteurs de relief partiels. La campagne physique reste limitée aux 168 cellules du centre, soit 10,5 km².

## Validation

```sh
node --test --test-concurrency=2 game/tests/v67/core.test.cjs game/tests/v68/*.test.cjs game/tests/v69/*.test.cjs game/tests/v70/*.test.cjs game/tests/v71/*.test.cjs game/tests/v72/*.test.cjs
python3 -m unittest discover -s game/tests/v70 -p 'test_*.py'
python3 -m unittest discover -s game/tests/v72 -p 'test_*.py'
python3 -S lancer.py --verify
```

Définir `MASSILIA_ROUTE_WORLD` vers le manifeste préparé exerce les vrais graphes AMP. Le corpus de routage70 est également rejoué contre72 en mémoire, avec ses assertions de source intactes et ses seules adaptations de planification documentées. Les quatre tests historiques du lanceur71 ont été exécutés sur sa vraie commande du commit `e348ace`, sans modifier leurs assertions ; le lanceur actuel est vérifié par les tests72.

Le [rapport de livraison](data/v72/FEATURE_REPORT.json) consigne les empreintes, résultats et preuves. Les sources 67–71, 27 originaux et données métropolitaines restent conservés. La fidélité architecturale 1:1 complète reste un chantier : façades, toitures, largeurs et ouvrages encore inconnus requièrent des relevés ou sources supplémentaires.

Un [smoke navigateur dédié à v72](tests/v72/browser_smoke.cjs) vérifie aussi le démarrage, le Cortex, l’export/import réel d’une sauvegarde de test, le rechargement, les inspecteurs du survol et le retour à la campagne dans un profil isolé. Playwright est une dépendance facultative de QA. Les commandes et limites figurent dans la [procédure de validation](../docs/development/VALIDATION.md) ; les résultats du correctif de couverture et de ce parcours sont consignés séparément dans le [rapport d’application des guides](../docs/development/APPLICATION_V72.md).
