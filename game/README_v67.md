# SOMA//MASSILIA 0.67 — Quartiers vivants

## Jouer
Extraire entièrement le ZIP puis lancer `LANCER_JEU.cmd` sous Windows avec Python 3.11+ installé. Sous Linux/macOS : `python tools/serve_game.py`. Le serveur écoute uniquement `127.0.0.1:8765`. Le jeu courant est `SOMA_MASSILIA_URBAIN_v0_67.html`.

## Cette passe
La v0.67 conserve la carte réelle, le relief, les POI, les sauvegardes, le guidage, les voyages rapides et l'interface rationalisée de la v0.66. Elle ajoute une couche de cohérence du monde vivant sans modifier les sources géographiques :

- textes d'ambiance contextuels écrits par district, heure, météo et pression policière ;
- conversation locale optionnelle pour les civils génériques, en laissant l'accès aux dialogues historiques ;
- panneau `État du quartier` enrichi par le rythme local, les présences simulées et les incidents disponibles ;
- régulation de la vitesse du trafic généré selon pluie, brouillard, tempête, heure de pointe et niveau de réponse policière ;
- réglage `Vie du monde & densité visuelle` : Économe / Standard / Dense. Il ne retire aucune entité ni donnée : il agit uniquement sur la distance de rendu des éléments ambiants ;
- densité visuelle bornée pour civils génériques, véhicules non prioritaires, robots non hostiles et animaux. Les acteurs nommés, policiers, hostiles, véhicules du joueur et unités d'intervention gardent leur priorité.

Ces systèmes sont additifs. Les campagnes, incidents, inventaire, flotte, carte de joueur, navigation OSM, voyage rapide, sauvegarde groupée et espace développeur v0.66 sont conservés dans le HTML de base.

## Périmètre géographique
Cette version ne prétend pas ajouter de nouvelle cartographie : elle conserve le périmètre et les données incorporées par la base v0.66. Les textes d'ambiance sont du contenu fictionnel de gameplay ; ils ne modifient ni coordonnées, ni routes, ni bâtiments, ni relief.

## Reconstruction
`python build.py` vérifie l'empreinte du HTML v0.66 gelé dans `baseline/v66.html`, puis ajoute le module lisible `src/v67/world-runtime.js`.

Tests ciblés :
- `node --check src/v67/world-runtime.js`
- `node tests/v67/core.test.cjs`

Le navigateur du conteneur bloque la navigation locale et le chargement complet de l'HTML via `set_content` dépasse le délai de ce banc ; cette édition n'est donc pas présentée comme une qualification WebGL/GPU complète.
