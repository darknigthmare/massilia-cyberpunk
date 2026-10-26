# Déplacer et réinstaller le cache AMP

`world_bundle.py` transporte le cache préparé désigné par son `manifest.json` :
vecteurs, relief, surfaces, navigation lorsqu’elle est présente, parties de
bâtiments et autres assets JSON référencés. Les acquisitions PBF/IGN et les
catalogues de fabrication restent dans leur stockage source.

Le module est autonome et utilise exclusivement la bibliothèque standard de
Python 3.10 ou ultérieur. Il peut être copié avec le paquet pour une réinstallation
hors ligne. La publication atomique de dossiers est prise en charge sous Linux
avec `renameat2(RENAME_NOREPLACE)` et sous Windows ; les autres plateformes sont
refusées avant publication. Aucun réseau n’est utilisé.

## Préparer et exporter

Depuis la racine du dépôt, sous Linux :

```sh
python3 -S game/tools/metropole/world_bundle.py plan --world game/data/v69/metropole
python3 -S game/tools/metropole/world_bundle.py export --world game/data/v69/metropole --output /tmp/amp-cache.mwb --progress
python3 -S game/tools/metropole/world_bundle.py verify --bundle /tmp/amp-cache.mwb
```

Sous Windows, remplacer `python3` par `py -3` et choisir un chemin de sauvegarde
local. Le fichier exporté doit se trouver hors du cache source.

`plan` contrôle le manifeste, les chemins, les descripteurs, les fichiers réguliers
et leurs tailles. Il indique `assetsHashed:false`. `export --plan` fournit la même
estimation sans créer de paquet. `verify --world` vérifie les SHA de tous les assets
du cache existant.

L’export vérifie chaque SHA pendant la copie. Il crée deux fichiers :

- `amp-cache.mwb` : paquet complet déterministe ;
- `amp-cache.mwb.receipt.json` : empreinte SHA256 externe du paquet, empreinte du
  manifeste brut, sources, tailles et nombre d’assets.

Conserver et déplacer ces deux fichiers ensemble. La commande `verify` lit
automatiquement le reçu adjacent. Un reçu déplacé peut être fourni avec
`--receipt`. `--sha256` et `--manifest-sha256` permettent de vérifier des empreintes
connues indépendamment. Pour un cache directement présent sur disque,
`verify --world` accepte `--manifest-sha256`.

## Réinstaller

Sur une installation fraîche dont le cache est absent :

```sh
python3 -S game/tools/metropole/world_bundle.py import --bundle /tmp/amp-cache.mwb --destination game/data/v69/metropole --progress
python3 -S game/tools/metropole/world_bundle.py verify --world game/data/v69/metropole
```

Le dossier destination doit être absent. Une installation déjà équipée peut
utiliser un autre dossier, par exemple `game/data/v69/metropole-restored`.
Le cache existant est conservé ; aucun remplacement implicite n’est effectué.
L’import conserve exactement les bytes du manifeste et des assets, y compris les
états de préparation, les références de sources et les données NoData.

L’import écrit dans un dossier temporaire voisin, vérifie chaque SHA, le footer
et le reçu éventuel, puis publie le dossier par un renommage atomique exclusif.
Une interruption Python nettoie la préparation. Un arrêt forcé peut laisser un
dossier temporaire, sans publier de cache partiel. L’export publie son reçu avant
le paquet complet ; un arrêt forcé peut laisser un reçu orphelin.

## Bornes et espace

Les limites par défaut sont :

| Élément | Limite |
| --- | ---: |
| Payload total, manifeste compris | 8 Gio |
| Manifeste brut | 128 Mio |
| Asset encodé | 16 Mio |
| Taille décodée déclarée d’un asset | 64 Mio |
| Assets uniques | 400 001 |
| Header du paquet | 64 Kio |
| Tampon de copie | 1 Mio |

La mémoire comprend aussi le manifeste brut, son JSON analysé et l’inventaire.
Le tampon de copie de 1 Mio ne représente donc pas la mémoire totale du processus.

`plan` distingue la taille logique du paquet et l’estimation d’allocation du cache
installé. Celle-ci arrondit chaque fichier à l’unité d’allocation du disque et
prévoit les entrées de répertoire. L’import utilise l’unité du disque destination,
contrôle les inodes disponibles lorsque le système les expose, et garde une
réserve de 64 Mio. La présence de nombreux petits fichiers augmente l’espace
physique nécessaire. Les options `--max-total-bytes`, `--max-asset-bytes` et
`--max-assets` permettent d’imposer des bornes adaptées.

## Format version 1

L’extension conseillée est `.mwb`. Le flux contient, dans cet ordre :

1. La constante `MAGIC` et un entier non signé de 32 bits, ordre réseau, indiquant
   la taille du header JSON canonique.
2. Ce header : schéma `soma-metropole/world-bundle/1`, SHA et taille du manifeste
   brut, seal du manifeste, empreintes PBF/pack source, compte et taille des assets,
   taille totale et SHA du module exporteur.
3. Les bytes exacts du manifeste mondial scellé.
4. Les bytes exacts des assets, par chemin relatif ASCII trié. Leur taille et leur
   SHA proviennent du manifeste ; aucun second index n’est stocké.
5. La constante `FOOTER`, puis les 32 octets du SHA256 de tout le préfixe précédent.

Aucun octet supplémentaire n’est admis. Les gzip existants sont transportés sans
décompression ni recompression. À manifeste, assets et source du module identiques,
les exports ont exactement les mêmes bytes ; noms de sauvegarde, dates, droits et
propriétaires du système de fichiers ne sont pas sérialisés.

Les chemins absolus, traversées `..`, séparateurs non portables, périphériques
Windows réservés, collisions après normalisation de casse, collisions fichier/
répertoire et liens symboliques sont refusés. Les références répétées à un même
asset sont dédupliquées seulement si leurs descripteurs sont identiques.

La validation conserve la signification des preuves et états du cache préparé.
Les contrôles géométriques de fabrication restent associés à leurs manifests et
rapports source, dont les bytes et empreintes sont préservés.

## API et tests

Les fonctions publiques sont `plan`, `export_bundle`, `verify_bundle`,
`verify_world` et `import_bundle`. `Limits` configure les budgets. Les fonctions
de copie et de vérification acceptent un callback `progress` ; ses exceptions
interrompent la préparation sans remplacer une destination existante.

```sh
python3 -S -m unittest game.tests.metropole.test_world_bundle -v
```
