# Entraîner un mot

Ce tutoriel fabrique un modèle de mot d’appel, du choix du mot au fichier ONNX. Il s’adresse à la personne qui a [préparé la machine](installer.md) : Docker installé, dépôt cloné. Aucune connaissance en apprentissage automatique n’est nécessaire.

La configuration fournie, `training.yml`, vise déjà « Cornelius ». Pour reconstruire ce modèle, sautez directement à l’[étape 3](#3-lancer-lentraînement).

## 1. Choisir le mot

Un bon mot d’appel :

- se prononce d’une seule façon, sans hésitation ;
- compte trois syllabes ou plus : un mot court ressemble à trop d’autres ;
- s’entend rarement dans une conversation ou à la télévision.

Une courte expression convient aussi (« Bonjour Cornelius »), tant qu’elle se dit d’une traite, en moins de deux secondes.

## 2. Remplir `training.yml`

Trois champs suffisent. Les autres réglages sont expliqués dans [Les réglages](reglages.md), et ceux d’origine conviennent pour commencer.

### Le nom du modèle

```yaml
model_name: barnabe
```

C’est le nom du fichier produit, `output/barnabe.onnx`, et du dossier de travail, `output/barnabe/`. Il commence par une lettre minuscule, puis compte au plus 63 minuscules ASCII, chiffres, `_` ou `-`. Gardez un nom différent pour chaque mot, et pour chaque nouvel essai d’un même mot.

### Les graphies du mot

```yaml
target_phrase:
  - "Barnabé"
  - "Barna bé"
```

Les voix de synthèse lisent du texte : elles prononcent ce qui est écrit, pas ce que vous entendez. Plusieurs graphies font varier la prononciation et rapprochent les clips de la façon dont le mot sera vraiment dit. Chaque graphie reçoit la même part des exemples.

Celles de « Cornelius » le montrent : « Corneliusse » fait entendre le s final, « Cornailius » ouvre le e (« nè » plutôt que « né »).

> [!TIP]
> Une graphie n’assure pas la prononciation voulue. Écoutez quelques clips avant d’entraîner : voir [Écouter les premiers clips](#écouter-les-premiers-clips).

### Les mots proches

```yaml
custom_negative_phrases:
  - "Barbara"
  - "Barnum"
  - "Bernadette"
  - "Panaché"
  - "Abbé"
```

Ce sont des mots qui ressemblent au mot d’appel et qui ne doivent **pas** le déclencher. Le modèle apprend à les distinguer. Pensez aux mots qui partagent une syllabe, une rime ou le même rythme, et aux prénoms de la maison. Aucun ne doit être identique à une graphie du mot.

Pour « Cornelius » : Cornélia, Cornélio, Corneille, « Corne du lys », Aurélie, Cornel, « Corneille et Louis ».

## 3. Lancer l’entraînement

Sous Windows, dans PowerShell, depuis le dossier du dépôt :

```powershell
.\build.ps1
```

Sous Linux :

```sh
./build.sh
```

Sans GPU NVIDIA, ajoutez `-Cpu` (Windows) ou `--cpu` (Linux).

Le script construit l’image Docker si elle manque, puis enchaîne quatre étapes :

| Étape | Ce qui se passe | Durée |
|---|---|---|
| `prepare` | télécharge les voix, les sons de fond, les réponses de pièces et les caractéristiques négatives | longue la première fois (18 Go en tout), immédiate ensuite |
| `generate` | fait dire le mot et les mots proches aux voix françaises : 44 000 clips WAV | une dizaine de minutes, sur le processeur (16 processus en parallèle) |
| `augment` | ajoute bruit et réverbération, puis calcule les caractéristiques des clips | une dizaine de minutes, sur le processeur |
| `train` | entraîne le modèle, puis l’exporte en ONNX | plus rapide avec un GPU |

Le premier entraînement prend donc du temps : laissez-le tourner. Le détail de chaque étape est dans [Comment ça marche](fonctionnement.md).

À la fin, le terminal affiche :

```text
Modèle prêt : /workspace/output/barnabe.onnx
Modèle ONNX prêt dans output/.
```

## Écouter les premiers clips

Pour un mot jamais essayé, écoutez les clips avant d’y passer des heures. Dès que la génération a fait ses premiers clips (la ligne `1000/20000`), lancez dans un autre terminal `.\build.ps1 -Config <recette>.yml -Etape ecoute` (ou `./build.sh ecoute --config=<recette>.yml`) : douze clips de chaque dossier arrivent dans `output/<model_name>-ecoute/`. Écoutez ceux de `positive_train/` : les quatre voix s’y succèdent, avec chaque graphie.

Les mots proches suivent dans `negative_train/`, une fois les 20 000 clips du mot faits.

Si une voix prononce mal le mot : `Ctrl+C`, corrigez `training.yml`, **changez `model_name`**, puis relancez. Le dossier de l’essai abandonné, `output/<ancien nom>/`, peut être supprimé.

Pour vous arrêter après la génération et écouter à loisir, lancez cette seule étape, puis la suite :

```powershell
.\build.ps1 generate
.\build.ps1
```

```sh
./build.sh generate
./build.sh
```

Les clips déjà générés sont gardés : la seconde commande ne fait que l’augmentation et l’entraînement. Chaque étape (`prepare`, `generate`, `augment`, `train`) se lance ainsi en la nommant.

## Suivre l’avancement

Pendant la génération, le terminal affiche une ligne tous les 100 clips. Dans un autre terminal, à tout moment :

```powershell
.\build.ps1 doctor
```

`doctor` fait le point sans rien modifier : clips générés pour chaque ensemble, sons de fond et réponses de pièces trouvés, caractéristiques présentes, modèle présent ou absent.

```text
Python : 3.10.12
Script officiel : /opt/openWakeWord/openwakeword/train.py (OK)
positive_train: 12400/20000
negative_train: 0/20000
positive_test: 0/2000
negative_test: 0/2000
rir_paths: /workspace/data/rir (270 WAV)
background_paths: /workspace/data/background (500 WAV)
Features: /workspace/data/features/openwakeword_features_ACAV100M_2000_hrs_16bit.npy (17280000128)
Features: /workspace/data/features/validation_set_features.npy (184836608)
Modèle: /workspace/output/barnabe.onnx (absent)
```

Les chemins sont ceux du conteneur : `/workspace` est le dossier du dépôt.

## Interrompre et reprendre

`Ctrl+C` arrête tout. Relancez la même commande pour reprendre :

- les **téléchargements** reprennent là où ils s’étaient arrêtés ;
- la **génération** garde les clips complets et ne fait que ceux qui manquent ;
- l’**augmentation** est sautée si ses quatre fichiers sont complets, sinon elle recommence depuis le début ;
- l’**entraînement** recommence depuis le début.

## Le résultat

| Fichier | Contenu |
|---|---|
| `output/<model_name>.onnx` | **le modèle**, environ 200 Ko : le seul fichier à garder |
| `generation.json` (dossier de travail) | la provenance des clips : graphies, mots proches, voix |
| `positive_train/`, `positive_test/` (dossier de travail) | les clips du mot |
| `negative_train/`, `negative_test/` (dossier de travail) | les clips des mots proches |
| `*_features_*.npy` (dossier de travail) | les caractéristiques calculées par l’augmentation |
| `output/<model_name>-ecoute/` | quelques clips copiés par l’étape `ecoute` |

Le dossier de travail est `/travail/<model_name>/`, dans le volume Docker `wakeword-travail` : il pèse quelques Go. Une fois le modèle satisfaisant, il peut être supprimé ; il resservirait seulement pour réentraîner avec d’autres réglages :

```sh
docker run --rm -v wakeword-travail:/travail --entrypoint rm wakeword-fr-training -rf /travail/<model_name>
```

## Recommencer

| Je veux… | Je fais… |
|---|---|
| un autre mot, ou d’autres graphies ou mots proches | un nouveau `model_name`, puis `build` |
| les mêmes clips, avec d’autres réglages d’entraînement (`steps`, `layer_size`…) | je renomme ou déplace `output/<model_name>.onnx`, puis `.\build.ps1 train` |
| refaire l’augmentation (autres sons de fond, `augmentation_rounds`) | je supprime les `*_features_*.npy` du dossier de travail (commande dans [Réglages](reglages.md)), puis `build` |

Le générateur ne remplace jamais un modèle existant, et refuse de mélanger des clips générés avec d’autres graphies ou d’autres voix sous le même nom : voir [Dépannage](depannage.md).

## Ensuite

Essayez le modèle au micro, avec plusieurs personnes et à plusieurs distances : [Tester au micro](tester.md). Puis installez-le : [Utiliser le modèle](utiliser.md).
