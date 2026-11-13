# Publication web statique

La version courante de Massilia est une application HTML/JavaScript. Son serveur local est un serveur de fichiers ; l’hébergement public peut donc servir les mêmes octets sans fonction de session, base de données ou transformation du moteur.

Le projet Vercel cible `massilia-cyberpunk`, équipe `darknigthmares-projects`, domaine `massilia-cyberpunk.vercel.app`. La publication utilise le SHA source exact indiqué dans `/release.json`.

## Construire

```sh
python3 hosting/build_static.py
```

Le script réutilise uniquement un reçu officiel dont les sources, sorties et 168 cellules sont revérifiées. Sans reçu valide, il exécute `lancer.py --prepare-only`, qui restaure les payloads et applique les builders gelés jusqu’à 0.78. Les HTML générés ne sont jamais modifiés ni ajoutés au dépôt.

La sortie `vercel-dist/` contient le HTML courant, le survol courant et tous les fichiers de `game/data/`, avec leurs chemins relatifs. La route `/` est réécrite vers le vrai HTML ; le navigateur charge directement le jeu, sans lanceur à installer. Aucun ancien HTML, script Python, test ou code de préparation n’est servi par cette sortie.

`release.json` contient les empreintes des fichiers, le SHA Git, la version et le périmètre des données. La copie Git fournit **168 cellules / 10,5 km² du centre**. Le cache métropolitain complet hors Git n’est pas ajouté ni annoncé ; le jeu et son survol conservent leur repli explicite sur les données réellement disponibles.

## Vérifier

Le build natif et son reçu vérifient les parents et assets avant la copie. Après publication, comparer `/release.json`, le HTML et le manifeste géographique aux empreintes locales. Reprendre ensuite le parcours réel : entrée dans Marseille, déplacement, Cortex et cartographie, puis charger une cellule servie par l’hôte.

Le stockage du navigateur appartient à l’origine web : une partie de l’ancien serveur local n’apparaît pas automatiquement sur le domaine public. Les fonctions d’export/import déjà présentes dans le jeu restent la voie de transfert.

L’hébergement ne certifie pas une campagne complète ni une restitution architecturale 1:1. Les sources géographiques, détails interprétés, partie physique du centre et survol restent distingués par le moteur inchangé.

## Contrôle du 13 novembre 2026

La préparation officielle de la source `1866fc5a92ea98b9e77291f1c3c828a86aed2d1c` conserve le HTML 0.78 de 67 338 716 octets (SHA-256 `e550b4ed050a953b9a5f19180f451299d79ecd9e9c4eba4e2906fcbd16dd2af1`). La sortie statique contient 729 fichiers / 153 541 919 octets avant le manifeste de livraison.

Le smoke Chromium local a réellement démarré 0.78, rejoint la cellule du centre, déplacé le joueur de z=0 à z=1,39776 par le clavier, ouvert le Cortex, la carte et la fiche Carrefour City. Huit ressources gzip (vecteurs, relief, navigation et surfaces aux deux extrémités du manifeste) ont répondu 200, retrouvé leurs empreintes et été décodées dans le navigateur. Ce contrôle court ne prétend pas terminer la campagne.

```sh
node hosting/browser_smoke.mjs http://127.0.0.1:9408/SOMA_MASSILIA_URBAIN_v0_78.html
# Après publication :
node hosting/browser_smoke.mjs https://massilia-cyberpunk.vercel.app/
```

Le smoke utilise Node.js 22+ et un Chrome/Chromium installé ; ces outils ne sont pas requis pour jouer sur le site. Ses rapports et captures restent dans `hosting/.reports/`.
