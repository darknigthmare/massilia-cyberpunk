# v0.74 — Mobilité, soutien médical, Acte III et fondations

Cette édition poursuit quatre chantiers du jeu, avec les ressources et propriétaires existants. Les références *Syndicate*, *Cyberpunk 2077* et *E.Y.E: Divine Cybermancy* orientent le contre-jeu, les opérations et la lisibilité ; les mécaniques restent celles de Massilia.

## Lancer

```sh
python3 lancer.py --prepare-only
python3 lancer.py --verify
python3 lancer.py --no-browser
```

Python 3.11+ et WebGL 2 suffisent. Après préparation, `python3 game/tools/serve_v74.py --no-browser` sert directement `SOMA_MASSILIA_URBAIN_v0_74.html` et `metropole-viewer-v74.html`. Le lanceur contrôle les cinq payloads, 27 originaux, treize HTML, onze rapports et les assets du centre avant de réutiliser son reçu local. Les sources 67–73 restent gelées ; les HTML et rapports de build sont générés hors Git.

La base est le commit `c0df4fe` de la v0.73. Les itinéraires directs/guidés, radio de contacts observés, netrunner, Écho, inspecteurs et HUD hérités restent intégrés.

## Déplacement et véhicules terrestres

Dans les 168 cellules physiques du centre, les déplacements à pied suivent le relief par sous-pas d’au plus **12 cm**. Ils refusent les secteurs sans altitude, les pentes supérieures à **95 %** et les carrosseries orientées, y compris celles des cellules voisines déjà construites. Les traces et géométries source ne sont pas modifiées. Le temps de déplacement traité par appel est borné à 100 ms afin de limiter les traversées lors d’une interruption de trame.

Les contrôles sur les vrais propriétaires du moteur montrent le même parcours sur des pentes admissibles de 50 et 80 % à 30, 60 et 120 Hz. Ces expériences utilisent un relief synthétique identifié ; elles ne constituent pas une mesure de performances ni une certification des accès de Marseille.

La sortie d’un véhicule terrestre vérifie un emplacement proche, à **6 m maximum**, un gabarit debout, le sol et le chemin jusqu’à cet emplacement. Si aucun accès ne convient, le joueur reste au volant et doit repositionner le véhicule. La sortie ne se rabat plus sur une ancienne position éloignée. Monter ou descendre recale immédiatement la caméra en altitude NGF. Les appareils aériens, bateaux et zones non géographiques conservent leurs règles propres.

## Soutien médical et contre-jeu

Le médecin ennemi prépare ses soins pendant **1,2 seconde**. Il choisit un allié réellement blessé, de faction compatible et visible à moins de 16 m. Il ne se choisit pas lui-même, n’aide pas une faction ennemie et ne soigne pas à travers un obstacle. Plusieurs médecins réservent des cibles distinctes lorsque des préparations sont déjà actives.

Un coup reçu, une perte de vue de l’allié, un état incompatible ou une transition interrompent la préparation en consommant sa récupération. L’effet de **+18** et le délai historique de **3,2 s** restent appliqués par la branche médicale v32. Le médecin ne tire pas pendant cette préparation. Un contact radio qui réoriente la recherche du joueur n’annule pas à lui seul un soin déjà commencé sur un allié resté visible ; il n’accorde aucun droit de tir supplémentaire. **Maj+F2 — Écho** expose son avancement et le conseil tactique lorsqu’il est réellement visible, avec le coût et les limites habituels du scan.

Les préparations sont temporaires. La recharge déjà portée par `attackClock` est conservée dans les propriétaires de combat32/33 lors d’une sauvegarde ; le canal n’est jamais repris après chargement. La validation37 vérifie ce scalaire optionnel. Aucun domaine `core.v74`, réserve d’énergie ou propriétaire de dégâts n’est ajouté. Boss et ICE conservent leurs systèmes.

## Acte III : preuves, rencontres et remise

Les rencontres v45 produisaient des identifiants refusés par le validateur de campagne37 et leurs ennemis n’étaient pas restaurés depuis le registre de combat32. La v0.74 accepte uniquement les identités exactes issues des définitions d’opérations et d’appels, avec leur zone et leurs indices. Les identifiants inventés ou déplacés restent refusés, ainsi que les objets de butin et dégâts localisés sans provenance compatible.

La première opération **Asphalte fantôme** demandait une conduite vers un secteur haut sans liaison automobile depuis le port. La conduite et sa rencontre visent maintenant **Corniche — extérieur**, accessible par les liens déjà présents. Les cinq étapes de conduite du contenu ont été auditées ; aucun raccord nouveau n’est ajouté. Les quatre identités historiques de cette rencontre conservent leur compatibilité de zone, leur santé et leur état de défaite ; un objectif ancien peut être réorienté sans écraser une destination manuelle.

Les unités v45 reprennent leur santé, leur armure et leur état de défaite depuis le propriétaire de combat existant. Le rôle de lame utilise son vrai archétype v32. Le véhicule réellement conduit est conservé lorsqu’une étape reconstruit la scène. Les valeurs de santé maximale restent cohérentes avec la santé initiale des unités ; les anciens états à 151 PV pour un maximum de 150 reprennent leurs 151 PV sans résurrection d’un ennemi déjà vaincu.

Les étapes vérifient l’objectif présent, la portée et la visibilité natives, la fin du canal ou le transfert réel en véhicule. Un choix déjà utilisé ou capturé avant un import ne peut pas avancer une autre étape. La remise utilise la console existante du centre des opérations de **Station Zéro**. Depuis **Pause → Archives et continuité → Centre de commandement**, **Tracer la remise** guide le retour ; **Remettre** est disponible à la console. Récompense et réputation restent celles de l’opération, versées une seule fois par leur propriétaire v45.

## Deux fondations de toiture réconciliées

Les toits OSM `264740443` et `264740444` étaient partiellement engloutis dans un corps voisin : leurs bases NGF indépendantes différaient de celle de leur support. L’audit natif confirme un parent géométrique unique et des écarts de contour de 0,8 et 3,8 mm. La copie de rendu leur attribue la fondation interprétée du support `264740436`, à **3,2842 m NGF**, en conservant leurs hauteurs source de 23 m, minimum de 20 m et élévation de toit de 3 m.

Cette association est **dérivée des contours**, avec une borne de quantification OSM de 1 cm. Elle ne déclare ni relation OSM explicite ni précision de relevé. Tous les points des segments extérieurs doivent satisfaire la borne ; un parent ambigu ou incomplet, un trou, une source différente ou un datum manquant empêche la correction. L’inspecteur **I** affiche cette provenance.

Seuls les sommets verticaux des deux toits changent. Emprises, corps, cours, couleurs, routes, relief et autres parties restent conservés dans les douze cellules contrôlées. Le cache source n’est pas réécrit. Cette cohorte appartient au survol métropolitain ; la géométrie de campagne reste celle de son instantané historique.

## Validation

```sh
MASSILIA_ROUTE_WORLD=/chemin/vers/manifest.json node --test --test-concurrency=2 game/tests/v74/*.test.cjs
python3 -m unittest discover -s game/tests/v74 -p 'test_*.py'
python3 lancer.py --verify
node game/tests/v74/browser_smoke.cjs --chromium /chemin/vers/chromium --output test-results/v74
node game/tests/v74/browser_features.cjs --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_74.html --chromium /chemin/vers/chromium --output test-results/v74-features
node game/tests/v74/browser_mechanics.cjs --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_74.html --chromium /chemin/vers/chromium --output test-results/v74-mechanics
node game/tests/v74/continuity_browser.cjs --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_74.html --chromium /chemin/vers/chromium --output test-results/v74-continuity
node game/tests/v74/browser_progression.cjs --url http://127.0.0.1:8765/SOMA_MASSILIA_URBAIN_v0_74.html --chromium /chemin/vers/chromium --output test-results/v74-progression
```

Playwright et Chromium sont facultatifs pour la QA ; le jeu n’en dépend pas. Les contrôles utilisent des profils neufs et décrivent l’instrumentation ou les fixtures dans leurs rapports. Le test des caractéristiques métropolitaines nécessite le cache AMP installé ; le smoke principal peut qualifier le repli explicite sur le centre. Les suites historiques des lanceurs71/72/73 visent leurs vraies commandes ; le lanceur partagé actuel est testé par74. Le [rapport de livraison](data/v74/FEATURE_REPORT.json) consigne les résultats réellement obtenus.

Le territoire acquis conserve 92 communes et 52 020 cellules. La campagne physique reste limitée aux 168 cellules du centre, soit 10,5 km². Les fondations corrigées et les gabarits de jeu ne constituent pas une architecture intégrale relevée à 1:1 ni une traversée physique certifiée de toute la métropole. Façades, dimensions et ouvrages sans données suffisantes restent interprétés.
