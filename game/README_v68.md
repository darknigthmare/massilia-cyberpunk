# v0.68 — Marseille augmentée

Cette passe améliore l’architecture de la carte réelle existante dans l’ambiance
cyberpunk du projet et prépare sa continuité visuelle entre cellules. La géographie ne reçoit aucune extension :
168 cellules, 10,5 km², projection Lambert-93 EPSG:2154 et unités en mètres.
L’axe local X pointe vers l’est et Z vers le sud. Les altitudes IGN partagent
toujours le datum NGF-IGN69 de la livraison originale.

## Architecture et provenance

`src/v68/architecture-core.js` distingue les couleurs explicitement déclarées,
les palettes interprétées à partir des matériaux OSM et la palette régionale de
repli. Un matériau déclaré ne constitue pas une mesure colorimétrique de façade.
Les fenêtres et les volets sont des détails de jeu interprétés.
Les fenêtres allumées et les accents cyan, magenta ou ambre sont déterminés par
l’identifiant du bâtiment, l’étage et la position globale du panneau. Ils ne
changent pas avec l’ordre de construction des cellules et ne clignotent pas.
Ils sont explicitement distincts des couleurs et matériaux déclarés dans OSM.
Leur cadence est ancrée dans le repère métrique commun et découpée sur chaque
segment de mur : une frontière de cellule ne recentre pas la façade. La teinte
d’un mur dépend de son orientation plutôt que de son ordre dans le fragment.

Le rendu conserve les triangles préparés des toits et les seuls murs de contour
source. Il ne ferme pas les cours, ne crée pas de murs aux découpes de cellules
et ne déplace pas les empreintes pour faciliter le dessin. Les fondations et
l’altitude rigide commune restent gérées par le connecteur IGN existant.

Seuls les toits plats déclarés et les toits à un pan suffisamment renseignés
sont reconnus comme modélisés. Un toit à un pan demande `height`, `roof:height`
et `roof:direction`, ainsi qu’une référence canonique complète. La hauteur
totale comprend le toit ; l’égout vaut `height - roof:height`. La direction OSM
désigne la pente descendante : à 90°, le bord est est le plus bas.

Les références sont construites depuis tous les fragments du même identifiant,
empreinte géométrique et reçu source. Les arêtes de coupe ne peuvent pas fermer
artificiellement une chaîne de murs source incomplète. L’index de toit ne traite
que les objets à un pan et reste en cache entre les vues de la collection.

Les formes `gabled`, `hipped`, `pyramidal`, `dome` et les autres formes non
prises en charge restent à plat. Il n’y a pas de reconstitution automatique de
monuments complexes à partir d’un simple nom OSM.

## Routes, topographie et limites du 1:1

Le tracé des routes, les cours et les emprises bâties viennent des données
livrées. Les sources dénombrent 34 986 objets de bâti et 7 723 voies uniques ;
ces nombres comprennent des parties et des catégories différentes, pas autant
de bâtiments et de rues indépendants.

Cent voies possèdent une largeur OSM. Pour les autres, les largeurs restent
estimées à partir des voies de circulation ou de la classe routière. Les
escaliers ne sont pas des relevés marche par marche. Les ponts, tunnels et
passages nécessitant une altitude d’ouvrage restent soumis aux exclusions
prudentes existantes ; le MNT ne donne pas la hauteur de leur tablier.

Le pas de 25 m décrit l’espacement d’échantillonnage du relief, pas une garantie
de précision des rues, marches ou murs de soutènement. Les collisions et
occultations des bâtiments restent des prismes conservateurs jusqu’à leur
hauteur maximale, y compris sur les toits inclinés. Une partie de bâtiment peut
encore être masquée par le volume de son contour parent.

L’extension vers l’Estaque, les massifs, les Calanques, Aubagne et Cassis exige
de nouvelles cellules sourcées et les altitudes correspondantes. Le fichier
PBF fourni reste disponible pour poursuivre l’import ; cette version ne
présente pas ces territoires comme jouables.

## Reconstruction et sauvegarde

`build_v68.py` vérifie le SHA256 du HTML v0.67 avant toute transformation, ajoute
les sources v0.68 et étend précisément le validateur de continuité pour
`state.v67`. Les domaines de versions futures inconnues restent refusés.
Les fichiers de livraison v0.67, leur manifeste, le PBF et les données IGN ne
sont pas réécrits. `lancer.py --verify` contrôle à la fois les fichiers
originaux et la correspondance entre les sources v0.68 et le HTML généré.

Le profil « Néons & nuit méditerranéenne » utilise une préférence visuelle locale.
L’ancienne valeur `wasteland` est migrée vers `cyberpunk` ; le choix `neutral`
est conservé. Le profil ne change ni le terrain ni les coordonnées et n’ajoute
pas de domaine à la sauvegarde de campagne. Le mode « Sans filtre » retire
l’étalonnage coloré, tout en gardant les lumières de façade.

Les panneaux lumineux réutilisent la géométrie des fenêtres et des appuis. Le
shader reconnaît leurs couleurs marquées et les dessine sans ombrage directionnel.
Ce sont des surfaces autolumineuses : il n’y a pas de nouvelle lumière dynamique,
de reflet calculé par lancer de rayons ou de bloom. Les autres matériaux restent
soumis à l’éclairage existant.
Les compteurs de diagnostic `litWindows` et `neonPanels` portent sur les panneaux
dessinés par cellule ; un panneau découpé ne représente pas plusieurs fenêtres
uniques.

Les tests couvrent la géométrie, les raccords, le rendu, l’intégrité et la
continuité. Le contrôle navigateur utilise le monde et le sauvegardeur réels,
dans un contexte neuf, et visite notamment `osm/way/265248513` dans la cellule
`V52-MC-W04-S01` : hauteur totale 9 m, base relative 6 m, toit 3 m, pente 210°.
