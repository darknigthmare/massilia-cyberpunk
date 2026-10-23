# Audit de livraison — SOMA//MASSILIA 0.67.0

## Filiation
La base exécutable est le HTML v0.66 exact, gelé dans `baseline/v66.html` et vérifié par SHA-256 `f1a6ce4b5957f634ff9fdbfaccfcf11c9e0d22159d01758dd56e29513581a014` (51 728 100 octets). L'arborescence de développement provient de l'archive v0.63 complète disponible dans l'espace de travail ; la v0.67 ajoute sa baseline v0.66 et un module lisible sous `src/v67/`.

## Portée fonctionnelle
La passe ne remplace aucune source OSM/IGN. Elle agit sur le comportement et la présentation : contexte de quartier, conversations ambiantes, régulation du trafic IA et densité visuelle.

Les acteurs nommés, policiers, hostiles, unités d'intervention et véhicule du joueur ne sont pas cachés par la densité ambiante. Le mode Économe réduit seulement les distances de rendu des civils génériques, véhicules secondaires, robots non hostiles et animaux ; la simulation et les tableaux d'entités restent intacts.

La vitesse du trafic généré est plafonnée par un facteur dépendant de la météo, des heures de pointe et de la pression policière. Les unités dispatch et véhicules spéciaux sont exclus de cette régulation.

## Contenu éditorial
Neuf familles de textes de quartier sont écrites à la main pour éviter des messages génériques : Station, Port, Corniche, Velours, Forge, Calanques, Relais, If et Couronne. Les variantes météo et police contextualisent les conversations et barks sans modifier les données cartographiques.

## Tests
- syntaxe JavaScript du module v0.67 : réussie (`node --check`) ;
- noyau ciblé Node : 10 contrôles réussis sur heure, météo, densité, trafic et état de quartier ;
- présence unique du module dans l'HTML construit et SHA du baseline contrôlés par le builder.

La tentative de navigation `file://` dans Chromium a été bloquée par `ERR_BLOCKED_BY_ADMINISTRATOR`. La tentative de charger le document complet (~52 Mo) via `page.set_content` a dépassé le délai de ce banc. Ces tentatives ne sont pas comptées comme des validations GPU ou navigateur intégrales.

## Limites
Pas de nouvelle zone, nouveau relevé IGN ou certification cartographique. Pas de qualification GPU physique, téléphone, manette ou campagne humaine complète. La simulation des foules reste locale aux zones construites et les routines détaillées de chaque civil ne sont pas devenues une simulation régionale persistante.
