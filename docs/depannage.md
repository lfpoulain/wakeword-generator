# Dépannage

Cette page part d’un symptôme ou d’un message, et dit quoi faire. Les messages du générateur commencent par `Erreur :`, ceux du testeur par `Testeur indisponible :`.

Pour savoir où en est un entraînement, commencez par :

```powershell
.\build.ps1 doctor
```

## Docker

### Docker ne répond pas

`docker: command not found`, `error during connect` ou `Cannot connect to the Docker daemon` : Docker n’est pas installé ou pas démarré. Sous Windows, lancez Docker Desktop et attendez qu’il soit prêt ; sous Linux, `sudo systemctl start docker`. Voir [Préparer la machine](installer.md).

### PowerShell refuse de lancer `build.ps1`

« L’exécution de scripts est désactivée sur ce système » : lancez le script ainsi, en ajoutant les options à la suite.

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

### Le GPU n’est pas vu

`could not select device driver "" with capabilities: [[gpu]]` : Docker ne sait pas transmettre la carte.

- **Linux** : installez le [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), puis redémarrez Docker.
- **Windows** : Docker Desktop doit utiliser le moteur WSL 2, avec un pilote NVIDIA à jour.

Vérifiez avec `docker run --rm --gpus all --entrypoint nvidia-smi wakeword-fr-training`. En attendant, l’option `-Cpu` (Windows) ou `--cpu` (Linux) entraîne sans GPU.

### `no kernel image is available for execution on the device`

La carte est trop récente pour CUDA 11.7 et PyTorch 1.13 (RTX 50, architecture Blackwell). Entraînez avec `-Cpu` ou `--cpu`.

### Le conteneur s’arrête sur `Killed`

Il a manqué de mémoire. Sous Windows, la mémoire de Docker est celle de WSL 2, réglable dans `%UserProfile%\.wslconfig` (clé `memory` de la section `[wsl2]`). Fermez les autres applications, ou baissez `augmentation_batch_size` dans `training.yml`.

### `No space left on device`

Il faut environ 40 Go libres, plus l’image Docker. Sous Windows, le disque virtuel de Docker Desktop grossit aussi : voir **Settings → Resources** de Docker Desktop.

### L’image ne prend pas en compte une mise à jour

Les scripts ne reconstruisent l’image que si elle manque. Après une mise à jour du `Dockerfile` :

```sh
docker build -t wakeword-fr-training .
```

## Les messages du générateur

| Message | Cause | Que faire |
|---|---|---|
| `Modèle déjà présent : … ; choisissez un autre model_name` | le générateur ne remplace jamais un modèle | renommez ou déplacez l’ancien `.onnx`, ou changez `model_name` |
| `La recette de génération, les phrases ou les voix ont changé ; choisissez un autre model_name…` | `training.yml` ne correspond plus aux clips déjà générés sous ce nom | changez `model_name`, ou supprimez le dossier de travail pour tout refaire : `docker run --rm -v wakeword-travail:/travail --entrypoint rm wakeword-fr-training -rf /travail/<model_name>` |
| `La recette a changé depuis la génération des clips` | même cause, à l’étape `augment` ou `train` | même remède |
| `… contient plus de clips que demandé ; choisissez un autre model_name…` | `n_samples` ou `n_samples_val` a été baissé | changez `model_name`, ou remettez la valeur d’avant |
| `Clips incomplets : … (12400/20000)` | `augment` ou `train` lancé avant la fin de la génération | lancez `generate`, ou `build` |
| `Provenance des clips absente : …/generation.json` | `augment` ou `train` lancé avant toute génération | lancez `build` |
| `Aucune voix française dans data/voices : lancez l’étape prepare`, `Voix Piper incomplète`, `Corpus WAV manquant` | données pas encore téléchargées | lancez `prepare`, ou `build` |
| `Téléchargement incomplet` | coupure réseau | relancez : le téléchargement reprend |
| `SHA-256 de voix Piper inattendu` | le fichier téléchargé n’est pas celui attendu | supprimez-le de `data/voices/` et relancez ; si le message revient, la voix a changé à la source : ouvrez un ticket |
| `Empreinte AudioSet invalide` | fragment AudioSet abîmé | supprimez `data/cache/audioset-bal-train-00.parquet` et relancez |
| `Clip Piper trop court après … essais` | une graphie ou un mot proche donne un son presque vide | réécrivez-le, en toutes lettres |
| `Accélération audio insuffisante` | l’expression est trop longue à dire | raccourcissez-la |
| `Une expression négative est identique au mot d'appel` | un mot proche reprend une graphie du mot | retirez-le de `custom_negative_phrases` |
| `model_name doit être un nom de fichier simple…` | majuscule, accent ou espace dans le nom | voir [Les réglages](reglages.md#le-mot) |
| `target_phrase doit être une liste de phrases non vides` | liste vide, ou mal indentée dans le YAML | une ligne `  - "…"` par graphie |

## Le testeur

| Message ou symptôme | Que faire |
|---|---|
| `Environnement du testeur absent` | installez-le : [Tester au micro](tester.md#installer-le-testeur) |
| `Testeur indisponible : Modèle absent : …` | entraînez d’abord le modèle, ou indiquez-en un avec `--model` |
| `Testeur indisponible : Empreinte SHA-256 incorrecte` | téléchargement abîmé : relancez le testeur |
| `No module named 'tkinter'` (Linux) | `sudo apt install python3-tk`, ou `sudo pacman -S tk` |
| `PortAudio library not found` (Linux) | `sudo apt install libportaudio2`, ou `sudo pacman -S portaudio` |
| « Aucun microphone détecté. » | branchez un micro, puis ↻. Sous Windows, autorisez l’accès au micro des applications de bureau (**Paramètres → Confidentialité et sécurité → Microphone**) |
| « Impossible de démarrer ce micro » | il n’accepte pas le son mono à 16 kHz. Sous Windows, un même micro apparaît plusieurs fois : essayez une autre ligne, souvent celle qui convertit d’elle-même (MME) |
| « Traitement trop lent ; écoute arrêtée. » | l’ordinateur est trop occupé : fermez d’autres applications et redémarrez l’écoute |
| Le score reste à zéro | vérifiez le micro choisi, parlez plus près, puis essayez le modèle de Cornelius avec `--model` pour écarter le modèle |

## Le modèle se comporte mal

| Symptôme | Pistes |
|---|---|
| Il manque des appels | baissez le seuil ; ajoutez des graphies plus proches de la façon dont le mot est dit ; écoutez les clips de `positive_train/` |
| Il se déclenche sur un mot précis | ajoutez ce mot à `custom_negative_phrases` et réentraînez |
| Il se déclenche tout seul, au hasard | montez le seuil ; augmentez `max_negative_weight` ; ajoutez vos propres bruits (voir [Les réglages](reglages.md#laugmentation)) |
| Il marche pour certaines voix seulement | les quatre voix de synthèse ne couvrent pas toutes les voix : essayez d’autres graphies, ou un seuil plus bas |

## Demander de l’aide

Ouvrez un ticket sur [le dépôt](https://github.com/lfpoulain/wakeword-generator/issues) avec :

- la sortie de `.\build.ps1 doctor` (ou `./build.sh doctor`) ;
- le message d’erreur complet ;
- votre système, et la carte graphique s’il y en a une ;
- votre `training.yml`.

Ne joignez ni clips, ni enregistrement de voix.
